import os
import requests
import json
import time
import re
from bs4 import BeautifulSoup
from datetime import datetime

# 基金成本基数
FUND_COST_BASE = 20000
# 成本技术分多少次投入
SHARE_COUNT = 100
# 每次投入的金额
SHARE_MONEY = FUND_COST_BASE / SHARE_COUNT
# 现金年化收益率
CASH_RATE = 0.01


def is_trade_day(date: str):
    # 读取 JSON 文件
    with open("../data/trade_day.json", "r") as f:
        data = json.load(f)

    # 获取当前年份
    current_year = datetime.now().strftime("%Y")

    # 检查当前日期是否在文件中
    if current_year in data and any(
        item["t_dt"] == date for item in data[current_year]
    ):
        return True
    else:
        return False


def is_tuesday_or_thursday(date_str: str, date_format: str = "%Y-%m-%d"):
    # 将字符串转换为 datetime 对象
    date = datetime.strptime(date_str, date_format)
    # 获取日期是星期几
    weekday = date.weekday()
    # 检查是否为周二、周三或周四
    return weekday in [1, 3]


def is_wednesday(date_str: str, date_format: str = "%Y-%m-%d"):
    date = datetime.strptime(date_str, date_format)
    return date.weekday() == 2


def update_index_data(index_code: str, date: str, max_retries: int = 5):
    """
    Updates the index data for a given index code and date.

    Args:
        index_code (str): The code of the index.
        date (str): The date for which the data needs to be updated.
        max_retries (int, optional): The maximum number of retries in case of request failure. Defaults to 5.

    Returns:
        dict: The updated index data.

    Raises:
        requests.exceptions.RequestException: If the maximum number of retries is exceeded.
    """
    timestamp_ms = int(time.time() * 1000)
    if index_code.startswith("000"):
        url = f"https://push2.eastmoney.com/api/qt/stock/get?invt=2&fltt=1&cb=jQuery35103551041611965715_{timestamp_ms}&secid=1.{index_code}"
    elif index_code.startswith("899"):
        url = f"https://push2.eastmoney.com/api/qt/stock/get?invt=2&fltt=1&cb=jQuery35106023423770896972_{timestamp_ms}&secid=0.{index_code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
    }

    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # 如果响应状态码不是 200，抛出异常
            break
        except requests.exceptions.RequestException as e:
            retries += 1
            print(f"Request failed: {e}. Retrying {retries}...")
    else:
        raise requests.exceptions.RequestException("Max retries exceeded")

    response_text = response.content.decode("utf-8")

    # 使用正则表达式删除函数调用
    json_text = re.sub(r"^\w+\((.*)\);$", r"\1", response_text)

    # 解析 JSON 数据
    try:
        data = json.loads(json_text)["data"]
    except json.JSONDecodeError:
        print("Failed to decode JSON data.")
        return None

    new_data = {
        "date": date,
        "pre_close": data["f60"] / 100,
        "open": data["f46"] / 100,
        "high": data["f44"] / 100,
        "low": data["f45"] / 100,
        "close": data["f43"] / 100,
        "change": (data["f43"] - data["f60"]) / 100,
        "change_percent": (data["f43"] - data["f60"]) / data["f60"] * 100,
        "trading_volume": data["f47"],
        "trading_value": data["f48"],
        "turnover_rate": data["f47"] * 100 / data["f85"] * 100,
    }

    file_path = f"../data/{index_code}.json"
    with open(file_path, "r+", encoding="utf-8") as f:
        try:
            index_data = json.load(f)
        except json.JSONDecodeError:
            print("Failed to decode JSON data.")
            return None

        # 查找给定日期的数据
        for item in index_data["market_data"]:
            if item["date"] == date:
                # 如果找到了，更新数据
                item.update(new_data)
                break
        else:
            # 如果没有找到，添加新的数据
            index_data["market_data"].append(new_data)

        # 将修改后的数据写回文件
        f.seek(0)
        json.dump(index_data, f, ensure_ascii=False, indent=4)
        f.truncate()

        print(f"Data for {index_code} on {date} has been updated.")

    return new_data


def update_fund_data(fund_code: str, date: str, max_retries: int = 5):
    url = f"https://fund.eastmoney.com/{fund_code}.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
    }

    session = requests.Session()
    for _ in range(max_retries):
        try:
            response = session.get(url, headers=headers)
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}. Retrying...")
    else:
        print("Max retries exceeded")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    data_item_02 = soup.find("dl", {"class": "dataItem02"})
    if data_item_02 is None:
        print("Failed to find data item.")
        return None

    data_date = data_item_02.find("dt").text.split(" ")[-1].strip("()")
    unit_value = data_item_02.find(
        "span", {"class": re.compile(r"ui-font-large ui-color-(red|green) ui-num")}
    ).text
    growth_rate = data_item_02.find_all(
        "span", {"class": re.compile(r"ui-font-middle ui-color-(red|green) ui-num")}
    )[0].text

    if data_date != date:
        print(
            f"The date of the fund {fund_code} data is {data_date}, current is {date}."
        )
        print(f"Failed to update data for {fund_code} {url} .")
        return None

    new_data = {"date": date, "unit_value": unit_value, "growth_rate": growth_rate}
    file_path = f"../data/{fund_code}.json"
    with open(file_path, "r+", encoding="utf-8") as f:
        try:
            fund_data = json.load(f)
        except json.JSONDecodeError:
            print("Failed to decode JSON data.")
            return None

        for item in fund_data["market_data"]:
            if item["date"] == date:
                item.update(new_data)
                break
        else:
            fund_data["market_data"].append(new_data)

        f.seek(0)
        json.dump(fund_data, f, ensure_ascii=False, indent=4)
        f.truncate()

    print(f"Data for {fund_code} on {date} has been updated.")
    return new_data


def load_market_data(fund_code: str):
    json_file = f"../data/{fund_code}.json"
    with open(json_file, "r") as f:
        return json.load(f)


def get_market_data(fund_code: str, date: str):
    data = load_market_data(fund_code)
    return next((item for item in data["market_data"] if item["date"] == date), None)


def get_last_market_data(fund_code: str):
    data = load_market_data(fund_code)
    return data["market_data"][-1]


def create_trade_detail(
    fund_code: str,
    date: str,
    trade_type: str = "buy",
    trade_money: float = 0,
    trade_fee: float = 0,
):
    trade_money = round(trade_money, 2)
    trade_fee = round(trade_fee, 2)

    market_data = get_market_data(fund_code, date)
    if market_data is not None:
        trade_price = round(float(market_data["unit_value"]), 4)
        trade_share = round(trade_money / trade_price, 4)
    else:
        trade_price = 0
        trade_share = 0

    return {
        "fund_code": fund_code,
        "trade_type": trade_type,
        "trade_money": trade_money,
        "trade_share": trade_share,
        "trade_price": trade_price,
        "trade_fee": trade_fee,
    }


def create_trade_record(date: str, trade_details: list):
    trade_money = sum(detail["trade_money"] for detail in trade_details)
    trade_fee = sum(detail["trade_fee"] for detail in trade_details)
    return {
        "date": date,
        "trade_money": trade_money,
        "trade_fee": trade_fee,
        "trade_detail": trade_details,
    }


def update_trade_records(new_record: dict):
    json_file = f"../data/portfolio-1_trade_records.json"
    # 读取现有的交易记录
    with open(json_file, "r") as f:
        records = json.load(f)

    # 检查是否存在相同日期的记录
    for record in records:
        if record["date"] == new_record["date"]:
            # 如果存在，更新记录
            record.update(new_record)
            break
    else:
        # 如果不存在，添加新的记录
        records.append(new_record)

    # 将更新后的交易记录写回文件
    with open(json_file, "w") as f:
        json.dump(records, f, indent=4)


def create_fund_detail(
    fund_code: str,
    date: str,
    share_change: float = 0,
    cost_change: float = 0,
):
    json_file = "../data/portfolio-1_change_records.json"
    with open(json_file, "r") as f:
        records = json.load(f)

    # 获取最后一条记录
    last_record = next(
        (item for item in records[-1]["fund_detail"] if item["fund_code"] == fund_code),
        None,
    )

    if last_record is not None:
        # 如果存在，更新记录
        market_data = get_market_data(fund_code, date)
        if market_data is not None:
            unit_value = round(float(market_data["unit_value"]), 4)
        else:
            unit_value = round(last_record["unit_value"], 4)
        share = round(last_record["share"] + share_change, 4)
        cost = round(last_record["cost"] + cost_change, 4)
        if share < 0:
            cumulative_cost = round(
                last_record.get("cumulative_cost", 0)
                + last_record["cost"]
                + share_change * unit_value,
                4,
            )
        else:
            cumulative_cost = round(
                last_record.get("cumulative_cost", 0) + cost_change, 4
            )
        value = round(share * unit_value, 2)
        earnings = round(value - cost, 2)
        cumulative_earnings = round(
            last_record.get("cumulative_earnings", 0) + earnings, 2
        )
    else:
        # 如果不存在，初始化记录
        unit_value = 0
        share = round(share_change, 4)
        cost = round(cost_change, 4)
        value = 0
        earnings = 0
        cumulative_earnings = 0

    return {
        "fund_code": fund_code,
        "date": date,
        "share": share,
        "cost": cost,
        "value": value,
        "unit_value": unit_value,
        "earnings": earnings,
        "cumulative_earnings": cumulative_earnings,
        "cumulative_cost": cumulative_cost,
    }


def create_change_record(date: str, fund_details: list):
    json_file = "../data/portfolio-1_change_records.json"
    with open(json_file, "r") as f:
        records = json.load(f)

    # 获取最后一条记录
    last_record = records[-1]
    days = (
        datetime.strptime(date, "%Y-%m-%d")
        - datetime.strptime(last_record["date"], "%Y-%m-%d")
    ).days
    fund_value_total = round(sum(detail["value"] for detail in fund_details), 2)
    fund_cost_total = round(sum(detail["cost"] for detail in fund_details), 2)
    cumulative_fund_value_total = round(
        sum(detail["cumulative_earnings"] for detail in fund_details)
        + fund_value_total,
        2,
    )
    cumulative_fund_cost_total = round(
        sum(detail["cumulative_cost"] for detail in fund_details) + fund_cost_total,
        2,
    )
    sell_value = 0
    for detail in fund_details:
        if detail["cost"] < 0.001:
            for fund in last_record["fund_detail"]:
                if fund["fund_code"] == detail["fund_code"]:
                    sell_value += detail["unit_value"] * fund["share"]
                    break
    balance = round(
        last_record["balance"] * (1 + CASH_RATE * days / 365)
        - fund_cost_total
        + sell_value,
        2,
    )
    return {
        "date": date,
        "balance": balance,
        "fund_value_total": fund_value_total,
        "fund_cost_total": fund_cost_total,
        "cumulative_fund_value_total": cumulative_fund_value_total,
        "cumulative_fund_cost_total": cumulative_fund_cost_total,
        "fund_detail": fund_details,
    }


def update_change_records(new_record: dict):
    json_file = f"../data/portfolio-1_change_records.json"
    # 读取现有的持仓数据
    with open(json_file, "r") as f:
        records = json.load(f)

    # 检查是否存在相同日期的记录
    for record in records:
        if record["date"] == new_record["date"]:
            # 如果存在，更新记录
            record.update(new_record)
            break
    else:
        # 如果不存在，添加新的记录
        records.append(new_record)

    # 将更新后的持仓数据写回文件
    with open(json_file, "w") as f:
        json.dump(records, f, indent=4)


def get_fund_gz_data(fund_code: str):
    if fund_code == "014533":
        print("Fund data is not available.")
        return None

    url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()  # 如果请求失败，这行代码会抛出异常

    response_text = response.content.decode("utf-8")
    json_text = re.sub(r"^\w+\((.*)\);$", r"\1", response_text)

    return json.loads(json_text)


def get_sell_funds():
    with open("../data/portfolio-1_change_records.json", "r") as file:
        change_data = json.load(file)

    funds = change_data[-1]["fund_detail"]
    sell_funds = []
    for fund in funds:
        if fund["cost"] < 0.001:
            continue
        return_rate = fund["value"] / fund["cost"]
        cost_rate = fund["cost"] / FUND_COST_BASE
        if (
            (cost_rate < 0.25 and return_rate > 1.08)
            or (cost_rate < 0.5 and return_rate > 1.1)
            or (cost_rate < 0.75 and return_rate > 1.12)
            or (cost_rate < 1 and return_rate > 1.15)
            or (cost_rate < 1.5 and return_rate > 1.2)
            or (cost_rate < 2 and return_rate > 1.25)
            or return_rate > 1.3
        ):
            fund["cost_rate"] = cost_rate
            fund["return_rate"] = return_rate
            sell_funds.append(fund)

    return sell_funds


def update_data():
    # 获取当前日期
    current_date = datetime.now().strftime("%Y-%m-%d")
    # current_date = "2024-02-28"

    if is_trade_day(current_date):
        try:
            with open("../data/portfolio-1.json", "r") as file:
                portfolio_data = json.load(file)

            # 获取 index_code 和 fund_code
            index_codes = portfolio_data["index_code"]
            fund_codes = portfolio_data["fund_code"]

            # 对于每个 index_code，修改相应的 JSON 文件
            for index_code in index_codes:
                update_index_data(index_code, current_date)

            # 对于每个 fund_code，修改相应的 JSON 文件
            trade_details = []
            fund_details = []
            sell_funds = get_sell_funds()
            if sell_funds:
                for fund in sell_funds:
                    update_fund_data(fund["fund_code"], current_date)
                    trade_details.append(
                        create_trade_detail(
                            fund["fund_code"],
                            current_date,
                            "sell",
                            fund["value"],
                            0,
                        )
                    )
                    fund_details.append(
                        create_fund_detail(
                            fund["fund_code"],
                            current_date,
                            -fund["share"],
                            -fund["cost"],
                        )
                    )
                    fund_codes.remove(fund["fund_code"])

            for fund_code in fund_codes:
                if is_tuesday_or_thursday(current_date):
                    trade_details.append(
                        create_trade_detail(
                            fund_code, current_date, "buy", SHARE_MONEY, 0
                        )
                    )
                    fund_details.append(
                        create_fund_detail(
                            fund_code,
                            current_date,
                            trade_details[-1]["trade_share"],
                            trade_details[-1]["trade_money"]
                            + trade_details[-1]["trade_fee"],
                        )
                    )
                elif is_wednesday(current_date):
                    if fund_code not in ["014533", "007339"]:
                        trade_details.append(
                            create_trade_detail(
                                fund_code, current_date, "buy", SHARE_MONEY, 0
                            )
                        )
                        fund_details.append(
                            create_fund_detail(
                                fund_code,
                                current_date,
                                trade_details[-1]["trade_share"],
                                trade_details[-1]["trade_money"]
                                + trade_details[-1]["trade_fee"],
                            )
                        )
                    else:
                        fund_details.append(create_fund_detail(fund_code, current_date))
                else:
                    fund_details.append(create_fund_detail(fund_code, current_date))

            if trade_details:
                update_trade_records(create_trade_record(current_date, trade_details))

            update_change_records(create_change_record(current_date, fund_details))

            selling_funds = get_sell_funds()
            if selling_funds:
                fund_messages = "\n".join(
                    [
                        f"基金代码: {fund['fund_code']}, 收益率: {fund['return_rate']:.2f}%, 成本比例: {fund['cost_rate']:.2f}%"
                        for fund in selling_funds
                    ]
                )
                send_feishu_message_card(
                    f"{get_feishu_webhook_url()}",
                    f"{get_github_action_workflow()} #{get_github_action_run_number()}",
                    f"达到预期收益，准备卖出基金:\n{fund_messages}",
                )

            send_feishu_message_card(
                f"{get_feishu_webhook_url()}",
                f"{get_github_action_workflow()} #{get_github_action_run_number()}",
                "数据更新成功!",
            )

        except Exception as e:
            send_feishu_message_card(
                f"{get_feishu_webhook_url()}",
                f"{get_github_action_workflow()} #{get_github_action_run_number()}",
                f"数据更新失败: {e}",
                "red",
                "danger",
            )


def get_github_action_run_url():
    server = os.getenv("GITHUB_SERVER_URL")
    repo = os.getenv("GITHUB_REPOSITORY")
    run_id = os.getenv("GITHUB_RUN_ID")
    if server and run_id and repo:
        return f"{server}/{repo}/actions/runs/{run_id}"
    else:
        return None


def get_github_action_run_number():
    return os.getenv("GITHUB_RUN_NUMBER")


def get_github_action_workflow():
    return os.getenv("GITHUB_WORKFLOW")


def get_feishu_webhook_url():
    return os.getenv("FEISHU_WEBHOOK_URL")


def send_feishu_message_card(
    webhook_url: str,
    title: str,
    content: str,
    title_template: str = "green",
    button_type: str = "primary",
):
    headers = {"Content-Type": "application/json"}
    data = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "template": title_template,
                "title": {"content": title, "tag": "plain_text"},
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": content,
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"content": "查看详情", "tag": "plain_text"},
                            "type": button_type,
                            "url": get_github_action_run_url(),
                        }
                    ],
                },
            ],
        },
    }
    response = requests.post(webhook_url, headers=headers, data=json.dumps(data))
    response.raise_for_status()  # 如果请求失败，这行代码会抛出异常


if __name__ == "__main__":
    update_data()
