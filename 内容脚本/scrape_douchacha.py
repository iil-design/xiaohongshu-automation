"""
抓取抖查查热门文章（10篇），存入内容数据库。
用法：python scrape_douchacha.py
"""
import asyncio, json, sys, os
from pathlib import Path

# Add project root to path so we can import models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from models.content import SessionLocal, Content

OUTPUT = Path.home() / "Desktop" / "抖查查热门文章.docx"
BASE = "https://www.douchacha.com"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        print("1. 打开文章列表页...")
        await page.goto(f"{BASE}/article/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)

        articles = await page.evaluate("""
            () => Array.from(document.querySelectorAll('.article_content'))
                .map(el => ({
                    title: el.querySelector('h1')?.textContent?.trim() || '',
                    summary: el.querySelector('.TextE2')?.textContent?.trim() || '',
                    href: el.closest('a')?.href || ''
                }))
                .filter(x => x.title)
                .slice(0, 10)
        """)

        print(f"   找到 {len(articles)} 篇文章")

        full_articles = []
        for i, art in enumerate(articles, 1):
            print(f"2.{i} 获取: {art['title'][:40]}...")
            content = ""
            if art['href']:
                try:
                    await page.goto(art['href'], wait_until="load", timeout=20000)
                    await page.wait_for_timeout(2000)
                    content = await page.evaluate("""
                        () => {
                            const selectors = ['.article-body', '.article_content', '.content',
                                '[class*="article"]', '[class*="content"]', 'article', '.post-body',
                                '#content', '.detail-content', '.rich-text'
                            ];
                            for (const sel of selectors) {
                                const el = document.querySelector(sel);
                                if (el && el.textContent.trim().length > 200) {
                                    return el.textContent.trim();
                                }
                            }
                            return document.body.textContent.trim().substring(0, 5000);
                        }
                    """)
                except Exception as e:
                    content = f"[获取失败: {e}]"

            full_articles.append({
                "title": art['title'],
                "summary": art['summary'],
                "url": art['href'],
                "content": content[:5000]
            })

        await browser.close()

    # 写入内容数据库
    print("\n3. 写入内容数据库...")
    db = SessionLocal()
    saved = 0
    try:
        for art in full_articles:
            # 跳过标题已存在的
            existing = db.query(Content).filter(Content.title == art['title']).first()
            if existing:
                print(f"   跳过重复: {art['title'][:30]}...")
                continue
            item = Content(
                source_plat="douchacha",
                title=art['title'],
                body=art['content'],
            )
            item.set_tags([art['summary'][:50]] if art['summary'] else [])
            db.add(item)
            saved += 1
        db.commit()
        print(f"   已保存 {saved} 篇到 content.db（跳过 {len(full_articles) - saved} 篇重复）")
    finally:
        db.close()

    # 打印摘要
    print(f"\n===== 结果 =====")
    for i, art in enumerate(full_articles, 1):
        print(f"{i}. {art['title']}")
        print(f"   正文长度: {len(art['content'])} 字")


asyncio.run(main())
