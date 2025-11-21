import requests
import os
from bs4 import BeautifulSoup
import time
from tqdm import tqdm
import re


def fetch_pdf_links_from_arxiv(query="cat:cs.CV", max_results=100, start=0):
    """
    从arXiv API获取PDF下载链接

    参数:
        query: 搜索查询，默认为计算机视觉领域
        max_results: 最大结果数量
        start: 分页起始位置
    """
    base_url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": query,
        "max_results": max_results,
        "start": start
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "xml")
        entries = soup.find_all("entry")

        pdf_links = []
        for entry in entries:
            title = entry.title.text.strip()
            pdf_url = None

            # 查找PDF链接
            for link in entry.find_all("link"):
                if link.get("title") == "pdf" or link.get("type") == "application/pdf":
                    pdf_url = link.get("href")
                    break

            if pdf_url:
                # 替换为国内镜像以提高下载速度[citation:5]
                pdf_url = pdf_url.replace("https://arxiv.org/pdf/", "http://xxx.itp.ac.cn/pdf/")
                pdf_links.append((title, pdf_url))

        return pdf_links

    except requests.exceptions.RequestException as e:
        print(f"API请求失败: {e}")
        return []


def sanitize_filename(filename):
    """清理文件名，移除非法字符"""
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


def download_pdfs(pdf_links, save_dir="arxiv_papers", delay=1):
    """下载PDF文件并保存到本地"""
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    successful_downloads = 0
    failed_downloads = []

    for title, pdf_url in tqdm(pdf_links, desc="下载PDF文件"):
        try:
            # 添加延迟以避免请求过于频繁
            time.sleep(delay)

            response = requests.get(pdf_url, headers=headers, stream=True, timeout=30)

            if response.status_code == 200:
                # 清理文件名
                safe_title = sanitize_filename(title)
                # 限制文件名长度
                if len(safe_title) > 100:
                    safe_title = safe_title[:100]

                file_path = os.path.join(save_dir, f"{safe_title}.pdf")

                # 分块写入文件
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)

                successful_downloads += 1
            else:
                print(f"下载失败: {title} | 状态码: {response.status_code}")
                failed_downloads.append((title, pdf_url, f"HTTP {response.status_code}"))

        except Exception as e:
            print(f"下载出错: {title} | 错误: {e}")
            failed_downloads.append((title, pdf_url, str(e)))

    print(f"\n下载完成！成功: {successful_downloads}, 失败: {len(failed_downloads)}")


def batch_download_by_category(total_papers, papers_per_request):
    """
    批量下载论文

    参数:
        total_papers: 需要下载的总论文数
        papers_per_request: 每次请求的论文数量
    """
    all_pdf_links = []

    # 计算机科学相关分类
    categories = [
        "cat:cs.AI",  # 人工智能
        "cat:cs.CV",  # 计算机视觉
        "cat:cs.LG",  # 机器学习
        "cat:cs.CL",  # 计算语言学
        "cat:cs.NE",  # 神经网络
        "cat:cs.SE",  # 软件工程
        "cat:cs.CR",  # 密码学与安全
    ]

    for category in categories:
        print(f"正在获取分类 {category} 的论文...")

        num_requests = (total_papers // len(categories)) // papers_per_request + 1

        for i in range(num_requests):
            start_index = i * papers_per_request
            pdf_links = fetch_pdf_links_from_arxiv(
                query=category,
                max_results=papers_per_request,
                start=start_index
            )
            all_pdf_links.extend(pdf_links)

            print(f"已获取 {len(pdf_links)} 篇论文链接")
            time.sleep(3)  # 避免请求过于频繁

            if len(all_pdf_links) >= total_papers:
                break

        if len(all_pdf_links) >= total_papers:
            break

    # 去重
    unique_links = list(set(all_pdf_links))
    print(f"总共获取到 {len(unique_links)} 篇唯一论文")

    # 下载PDF
    download_pdfs(unique_links[:total_papers])


if __name__ == "__main__":
    # 下载论文

    print("开始批量下载...")
    batch_download_by_category(total_papers=10000, papers_per_request=1000)