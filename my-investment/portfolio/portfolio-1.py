import requests
import json
import time
import re
from bs4 import BeautifulSoup
from datetime import datetime


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
        json.dump(index_data, f, indent=4)
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
        print(f"Failed to update data for {fund_code} {url}.")
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
        json.dump(fund_data, f)
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

    trade_price = get_market_data(fund_code, date)
    if trade_price is not None:
        trade_price = round(float(trade_price["unit_value"]), 2)
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


def update_data():
    # 获取当前日期
    current_date = datetime.now().strftime("%Y-%m-%d")

    if is_trade_day(current_date):

        with open("../data/portfolio-1.json", "r") as file:
            portfolio_data = json.load(file)

        # 获取 index_code 和 fund_code
        index_codes = portfolio_data["index_code"]
        fund_codes = portfolio_data["fund_code"]

        # 对于每个 index_code，修改相应的 JSON 文件
        for index_code in index_codes:
            update_index_data(index_code, current_date)

        # 对于每个 fund_code，修改相应的 JSON 文件
        trade_detail = []
        for fund_code in fund_codes:
            update_fund_data(fund_code, current_date)
            if is_tuesday_or_thursday(current_date):
                trade_detail.append(
                    create_trade_detail(fund_code, current_date, "buy", 200, 0)
                )
            elif is_wednesday(current_date):
                if fund_code != "014533" or fund_code != "007339":
                    trade_detail.append(
                        create_trade_detail(fund_code, current_date, "buy", 200, 0)
                    )
        if is_tuesday_or_thursday(current_date) or is_wednesday(current_date):
            update_trade_records(create_trade_record(current_date, trade_detail))


if __name__ == "__main__":
    update_data()
