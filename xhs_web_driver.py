from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import time
import random
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains

import logging
import re
import json
from example import download_task
from asyncio import run

# 配置日志记录
logging.basicConfig(filename='xiaohongshu.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def check_and_wait_for_login(driver):
    try:
        # 检查是否弹出登录框，这里的选择器需要根据实际情况调整
        login_box = driver.find_element(By.CSS_SELECTOR, 'div[class*="login-modal"]')
        if login_box.is_displayed():
            print("检测到登录框，请手动完成登录，登录成功后程序将自动继续...")
            while True:
                try:
                    # 持续检查登录框是否还存在
                    login_box = driver.find_element(By.CSS_SELECTOR, 'div[class*="login-modal"]')
                    if not login_box.is_displayed():
                        break
                except Exception:
                    # 若找不到登录框元素，说明登录框已消失
                    break
                time.sleep(1)  # 每隔 1 秒检查一次
    except Exception:
        # 若未找到登录框，尝试点击登录按钮
        try:
            login_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, 'login-btn'))
            )
            login_button.click()
            print("点击登录按钮，请手动完成登录，登录成功后程序将自动继续...")
            while True:
                try:
                    # 持续检查登录框是否还存在
                    login_box = driver.find_element(By.CSS_SELECTOR, 'div[class*="login-modal"]')
                    if not login_box.is_displayed():
                        break
                except Exception:
                    # 若找不到登录框元素，说明登录框已消失
                    break
                time.sleep(1)  # 每隔 1 秒检查一次
        except Exception as e:
            print(f"点击登录按钮时出错: {e}")

# 提取脚本数据
def extract_script_data(driver, element_id):
    try:
        # 最多等待 2 秒，直到至少有一个 <script> 标签被找到
        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.TAG_NAME, 'script'))
        )

        # 获取所有script标签的内容
        scripts = driver.find_elements("tag name", "script")
        data = None        
        for script in scripts:
            script_content = script.get_attribute("innerHTML")
            if "window.__INITIAL_STATE__" in script_content:
                json_str = script_content.replace("window.__INITIAL_STATE__=", "")
                # 处理JavaScript中的undefined（替换为null）
                json_str = json_str.replace("undefined", "null")
                # 解析为Python字典
                data = json.loads(json_str)
                break  # 找到后退出循环        
        
        # 提取示例数据（例如global.appSettings）
        if data:
            noteDetail = data.get("note", {}).get("noteDetailMap", {}).get(element_id, {}).get("note", {})
            return noteDetail
        else:
            print("未找到目标数据")        
    except Exception as e:
        print(f"发生错误: {e}")

# 提取页面数据
def extract_page_info(driver, element_id, new_page: bool = True):
    # 获取当前页面的 URL
    current_url = driver.current_url
    print(f"当前页面 URL: {current_url}")    

    # 打印脚本数据
    noteDetail = None
    if new_page: 
        noteDetail = extract_script_data(driver, element_id)
    else:
        time.sleep(2)
        # 从浏览器监控日志获取网络数据
        logs = driver.get_log('performance')
        for log in logs:
            response_data = handle_response(driver, log)
            if response_data != None:
                item = response_data.get('data', {}).get('items', [])[0]
                print(item)
                if item.get('id') == element_id:
                    noteDetail = item.get("note_card", {})
                    break

    username = ''
    title = ''
    desc_text = ''
    tags_str = ''
    # 获取作者
    try:
        # 等待 span 元素可见，最长等待 10 秒
        username_element = WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.author-container div.author-wrapper div.info a.name span.username'))
        )
        username = username_element.text.strip()
    except Exception as e:
        print(f"获取作者: {e}")

    # 获取标题
    try:
        title_element = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.ID, 'detail-title'))
        )
        title = title_element.text.strip()
    except Exception as e:
        print("无标题获取标题")

    # 获取描述文本
    try:
        desc_text_element = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#detail-desc .note-text span'))
        )
        desc_text = desc_text_element.text.strip()
    except Exception as e:
        print("无描述文本")

    # 定位所有标签元素
    try:
        tag_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '#detail-desc .note-text a.tag'))
        )
        tags = [tag.text for tag in tag_elements]
        tags_str = ', '.join(tags)
    except Exception as e:
        print("无标签")    
   

    # 创建一个字典来存储这些参数
    data = {
        "current_url": current_url,
        "username": username,
        "title": title,
        "desc_text": desc_text,
        "tags_str": tags_str,
        "noteDetail": noteDetail
    }
    return data

# 详情页处理
async def process_detail_page(driver, node_item_element, processed_elements, new_page: bool = True):
    try:
        element_id = ""

        link_element = node_item_element.find_element(By.CSS_SELECTOR, 'div a.cover.ld.mask')
        # 获取链接
        link_url = link_element.get_attribute('href')
        # 定义正则表达式模式
        pattern = r'explore/([^?]+)\?'
        # 使用 re.search() 函数进行匹配
        match = re.search(pattern, link_url)
        # 检查是否匹配成功
        if match:
            # 提取捕获组中的内容
            element_id = match.group(1)
            print(f"提取到的 ID 是: {element_id}")
            if element_id in processed_elements:
                return
            processed_elements.add(element_id)
        else:
            print("未找到匹配的 ID。")
            return
        

        # 尽量滚动到屏幕中央位置, 代码加了之后有点问题。先注释掉
        # viewHeight = driver.execute_script("return Math.max(document.documentElement.clientHeight, window.innerHeight)")
        # bottom = driver.execute_script("return arguments[0].getBoundingClientRect().bottom", node_item_element)
        # print(f"{bottom}-------------->{viewHeight}")
        # if bottom + 200 > viewHeight:
        #     scroll_step = random.randint(180, 240)
        #     driver.execute_script(f"document.documentElement.scrollTop += {scroll_step};")

        # 滚动到元素位置
        actions = ActionChains(driver)
        actions.move_to_element(link_element).perform()
        time.sleep(random.uniform(1, 3))

        like_count_element = node_item_element.find_element(By.CSS_SELECTOR, 'div div.footer div.author-wrapper span.like-wrapper.like-active span.count')
        # 获取点赞数文本
        like_count_text = like_count_element.text.strip()

        # 处理带有 + 号的情况
        if "万" in like_count_text:
            # 如果点赞数带有 "万" 字，转换为具体数字
            like_count_text = like_count_text.replace("万", "").replace("+", "")
            like_count = float(like_count_text) * 10000
        elif "千" in like_count_text:
            # 如果点赞数带有 "千" 字，转换为具体数字
            like_count_text = like_count_text.replace("千", "").replace("+", "")
            like_count = float(like_count_text) * 1000
        elif "+" in like_count_text:
            # 如果点赞数带有 "+" 字，转换为具体数字
            like_count_text = like_count_text.replace("+", "")
            like_count = float(like_count_text)
        elif "" == like_count_text:
            return 
        else:
            like_count = int(like_count_text)

        if like_count > 3000:
            print(f"点赞数：{like_count}")                    
            
            if new_page:
                # 浏览器新标签方式打开：在新标签中打开详情页链接
                driver.execute_script(f"window.open('{link_url}', '_blank');")
                # 切换到新打开的标签页
                driver.switch_to.window(driver.window_handles[-1])
            else:
                # 弹窗方式打开：点击链接打开内容详情页弹框
                link_element.click()
            
            data = extract_page_info(driver, element_id, new_page)


            downLoad = False
            if data["noteDetail"] != None:
                noteDetail = data["noteDetail"]
                if noteDetail.get("type","") == "video":
                    duration = noteDetail.get("video", {}).get("capa", {}).get("duration")
                    if duration < 50:
                        downLoad = True
                            
            # 将字典转换为 JSON 字符串
            json_str = json.dumps(data, ensure_ascii=False)

            print(f"笔记数据：{json_str}")

            if downLoad:
                try:
                    download_data = await download_task(data["current_url"])
                    print(download_data)
                    print("--------------------------------")
                except Exception as e:
                    print("下载失败")

            # 滚动评论
            note_scroller_element = driver.find_element(By.CSS_SELECTOR, 'div.note-scroller')
            scroll_count = random.randint(1, 2)
            is_clicked = True
            for _ in range(scroll_count):
                scroll_step = random.randint(85, 120)
                # 每次滚动随机像素
                driver.execute_script(f"arguments[0].scrollTop += {scroll_step};", note_scroller_element)
                
                if not is_clicked:
                    try:
                        # 查看更多评论
                        show_more_element = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.show-more"))
                        )
                        print(f"存在更多回复: {show_more_element.text}")
                        show_more_element.click()
                        is_clicked = True
                    except Exception as e:
                        print("不存在更多回复")

                time.sleep(random.uniform(1,3))

            if new_page:
                # 关闭浏览器详情页链接标签
                driver.close()
                # 切换回列表页
                driver.switch_to.window(driver.window_handles[0])
            else:
                # 关闭详情弹框
                try:
                    close_quit_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "div.close-circle"))
                    )
                    close_quit_button.click()
                    print("关闭弹框成功")
                except Exception as e:
                    print(f"关闭弹框时出错: {e}")

            print("======================================================")
        time.sleep(random.uniform(1, 3))        
    except Exception as e:
        print(f"An error occurred 1: {e}")
    finally:
        pass    

# 定义处理网络响应的回调函数
def handle_response(driver, log):
    try:
        message = json.loads(log['message'])['message']
        if message['method'] == 'Network.responseReceived':
            response_data = message['params']['response']
            if response_data['url'] == 'https://edith.xiaohongshu.com/api/sns/web/v1/feed':
                request_id = message['params']['requestId']
                try:
                    # 获取响应体
                    body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                    # 解析响应体为 JSON 数据
                    json_data = json.loads(body['body'])
                    return json_data
                except json.JSONDecodeError:
                    print("响应体不是有效的 JSON 格式。")
                except Exception as e:
                    print(f"Error getting response body for requestId {request_id}")
    except (KeyError, json.JSONDecodeError):
        pass

async def process_page():
    # 指定 ChromeDriver 的路径
    chrome_driver_path = r'C:\huyang\huyang\chromedriver\chromedriver.exe'
    service = Service(chrome_driver_path)

    # 创建 Chrome 选项
    chrome_options = Options()
    chrome_options.add_experimental_option('perfLoggingPrefs', {'enableNetwork': True})
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})    # 禁用浏览器的自动关闭功能
    chrome_options.add_experimental_option("detach", True)

    # 创建 Chrome 浏览器实例
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # 打开小红书探索页面
        url = 'https://www.xiaohongshu.com/explore?channel_id=homefeed_recommend'
        driver.get(url)

        # 首次检查登录框或点击登录按钮
        check_and_wait_for_login(driver)

        # 用于记录已经处理过的元素的唯一标识
        processed_elements = set()

        while True:
            # 定位所有元素
            node_item_elements = driver.find_elements(By.CSS_SELECTOR, 'section.note-item')
            # 获取找到的元素的个数
            element_count = len(node_item_elements)
            print(f"找到了 {element_count} 元素")        

            for node_item_element in node_item_elements:
                await process_detail_page(driver, node_item_element, processed_elements, False)                        

            if len(processed_elements) > 200:
                processed_elements.clear()

            # 向下翻页    
            # 使用ActionChains进行滚动
            actions = ActionChains(driver)
            actions.send_keys(Keys.PAGE_DOWN).perform()
            time.sleep(random.uniform(6, 8))

    except Exception as e:
        print(f"An error occurred 2: {e}")
    finally:
        # 关闭浏览器
        # driver.quit()
        pass

if __name__ == '__main__':
    run(process_page())