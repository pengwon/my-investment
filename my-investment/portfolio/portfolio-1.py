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


def update_index_data(index_code: str, date: str):
    timestamp_ms = int(time.time() * 1000)
    if index_code.startswith("000"):
        url = f"https://push2.eastmoney.com/api/qt/stock/get?invt=2&fltt=1&cb=jQuery35103551041611965715_{timestamp_ms}&secid=1.{index_code}"
    elif index_code.startswith("899"):
        url = f"https://push2.eastmoney.com/api/qt/stock/get?invt=2&fltt=1&cb=jQuery35106023423770896972_{timestamp_ms}&secid=0.{index_code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
    }
    print(url)
    response = requests.get(url, headers=headers)
    response_text = response.content.decode("utf-8")

    # 使用正则表达式删除函数调用
    json_text = re.sub(r"^\w+\((.*)\);$", r"\1", response_text)
    print(json_text)

    # 解析 JSON 数据
    # f43：当前值
    # f44：最高
    # f45：最低
    # f46：今开
    # f47：成交量（手）
    # f48：成交额
    # f60：昨收
    # f85：流通股
    data = json.loads(json_text)["data"]
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
    # Add your code here to update the index data
    file_path = f"../data/{index_code}.json"
    with open(file_path, "r+", encoding="utf-8") as f:
        index_data = json.load(f)
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
        json.dump(index_data, f)
        f.truncate()


def update_fund_data(fund_code: str, date: str):
    url = f"https://fund.eastmoney.com/{fund_code}.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
    }
    response = requests.get(url, headers=headers)
    html = response.text

    soup = BeautifulSoup(html, "html.parser")

    data_item_02 = soup.find("dl", {"class": "dataItem02"})
    data_date = data_item_02.find("dt").text.split(" ")[-1].strip("()")
    unit_value = data_item_02.find(
        "span", {"class": re.compile(r"ui-font-large ui-color-(red|green) ui-num")}
    ).text
    growth_rate = data_item_02.find_all(
        "span", {"class": re.compile(r"ui-font-middle ui-color-(red|green) ui-num")}
    )[0].text

    if data_date == date:
        new_data = {"date": date, "unit_value": unit_value, "growth_rate": growth_rate}
        file_path = f"../data/{fund_code}.json"
        with open(file_path, "r+", encoding="utf-8") as f:
            fund_data = json.load(f)
            # 查找给定日期的数据
            for item in fund_data["market_data"]:
                if item["date"] == date:
                    # 如果找到了，更新数据
                    item.update(new_data)
                    break
            else:
                # 如果没有找到，添加新的数据
                fund_data["market_data"].append(new_data)

            # 将修改后的数据写回文件
            f.seek(0)
            json.dump(fund_data, f)
            f.truncate()

    return new_data


def update_portfolio_data(fund_data: dict, date: str):
    file_path = f"../data/portfolio-1.json"
    with open(file_path, "r+", encoding="utf-8") as f:
        portfolio_data = json.load(f)
        # 查找给定日期的数据
        for item in portfolio_data["change_records"]:
            if item["date"] == date:
                # 如果找到了，更新数据
                item.update(new_data)
                break
        else:
            # 如果没有找到，添加新的数据
            portfolio_data["market_data"].append(new_data)

        # 将修改后的数据写回文件
        f.seek(0)
        json.dump(portfolio_data, f)
        f.truncate()


def get_fund_data(fund_code: str, date: str):
    if fund_code != "014533":
        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
        }
        print(url)
        response = requests.get(url, headers=headers)
        response_text = response.content.decode("utf-8")
        response_text = response.content.decode("utf-8")
        print(response_text)
        # 使用正则表达式删除函数调用
        json_text = re.sub(r"^\w+\((.*)\);$", r"\1", response_text)

        # 解析 JSON 数据
        data = json.loads(json_text)
        print(data)
        new_data = {
            "date": date,
            "gsz": data["gsz"],
            "gszzl": data["gszzl"],
            "gsz_time": data["gztime"],
            "jzrq": data["jzrq"],
            "dwjz": data["dwjz"],
        }

        file_path = f"../data/{fund_code}.json"
        with open(file_path, "r+", encoding="utf-8") as f:
            fund_data = json.load(f)
            # 查找给定日期的数据
            for item in fund_data["market_data"]:
                if item["date"] == date:
                    # 如果找到了，更新数据
                    item.update(new_data)
                    break
            else:
                # 如果没有找到，添加新的数据
                fund_data["market_data"].append(new_data)

            # 将修改后的数据写回文件
            f.seek(0)
            json.dump(fund_data, f)
            f.truncate()


def update_market_data():
    # 获取当前日期
    current_date = datetime.now().strftime("%Y-%m-%d")

    if is_trade_day(current_date):

        with open("../data/portfolio-1.json", "r+") as file:
            portfolio_data = json.load(file)

            # 获取 index_code 和 fund_code
            index_codes = portfolio_data["index_code"]
            fund_codes = portfolio_data["fund_code"]

            # 对于每个 index_code，修改相应的 JSON 文件
            for index_code in index_codes:
                update_index_data(index_code, current_date)

            # 对于每个 fund_code，修改相应的 JSON 文件
            for fund_code in fund_codes:
                fund_data = update_fund_data(fund_code, current_date)
                fund_data["fund_code"] = fund_code
                
                for item in portfolio_data["change_records"][-1]["fund_detail"]:
                    if item["fund_code"] == fund_code:
                        # 如果找到了，更新数据
                        fund_data["share"] = item["share"]
                        break
                
                for item in portfolio_data["trade_records"][-1]["trade_detail"]:
                    if item["fund_code"] == fund_code:
                        # 如果找到了，更新数据
                        if item["trade_type"] == "buy":
                            fund_data["share"] += item["cost"]
                        elif item["trade_type"] == "sell":
                            fund_data["share"] -= item["cost"]
                        break
                
                portfolio_data["fund_detail"].append(fund_data)
            # 将修改后的数据写回文件
            file.seek(0)
            json.dump(portfolio_data, file)
            file.truncate()


if __name__ == "__main__":
    update_market_data()
