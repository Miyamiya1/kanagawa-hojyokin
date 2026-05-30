import urllib.request, urllib.parse, json, os, re
from html.parser import HTMLParser

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = os.environ["NOTION_DB_ID"]
CLAUDE_KEY = os.environ["CLAUDE_API_KEY"]

headers_notion = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 巡回対象（各自治体の補助金検索URL）
TARGETS = [
    {"area": "横浜市", "url": "https://www.city.yokohama.lg.jp/search/result.html?q=%E8%A3%9C%E5%8A%A9%E9%87%91"},
    {"area": "川崎市", "url": "https://www.city.kawasaki.jp/search/index.cgi?q=%E8%A3%9C%E5%8A%A9%E9%87%91"},
    {"area": "鎌倉市", "url": "https://www.city.kamakura.kanagawa.jp/search/result.html?q=%E8%A3%9C%E5%8A%A9%E9%87%91"},
    {"area": "藤沢市", "url": "https://www.city.fujisawa.kanagawa.jp/search/result.html?q=%E8%A3%9C%E5%8A%A9%E9%87%91"},
    {"area": "横須賀市", "url": "https://www.city.yokosuka.kanagawa.jp/search/result.html?q=%E8%A3%9C%E5%8A%A9%E9%87%91"},
    {"area": "平塚市", "url": "https://www.city.hiratsuka.kanagawa.jp/search/result.html?q=%E8%A3%9C%E5%8A%A9%E9%87%91"},
    {"area": "相模原市", "url": "https://www.city.sagamihara.kanagawa.jp/search/result.html?q=%E8%A3%9C%E5%8A%A9%E9%87%91"},
    {"area": "厚木市", "url": "https://www.city.atsugi.kanagawa.jp/search/result.html?q=%E8%A3%9C%E5%8A%A9%E9%87%91"},
    {"area": "茅ヶ崎市", "url": "https://www.city.chigasaki.kanagawa.jp/search/result.html?q=%E8%A3%9C%E5%8A%A9%E9%87%91"},
    {"area": "大和市", "url": "https://www.city.yamato.lg.jp/search/result.html?q=%E8%A3%9C%E5%8A%A9%E9%87%91"},
]

def get_existing_urls():
    urls = set()
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        req = urllib.request.Request(
            f"https://api.notion.com/v1/databases/{DB_ID}/query",
            data=json.dumps(body).encode(),
            headers=headers_notion, method="POST"
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read())
        for p in data["results"]:
            url = p["properties"]["公式URL"]["url"]
            if url:
                urls.add(url)
        if not data["has_more"]:
            break
        cursor = data["next_cursor"]
    return urls

def fetch_page(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.read().decode("utf-8", errors="ignore")
    except:
        return ""

def extract_links(html, base_url):
    links = []
    pattern = r'href=["\']([^"\']+)["\']'
    for match in re.finditer(pattern, html):
        href = match.group(1)
        if href.startswith("http"):
            links.append(href)
        elif href.startswith("/"):
            parsed = urllib.parse.urlparse(base_url)
            links.append(f"{parsed.scheme}://{parsed.netloc}{href}")
    return links

def ask_claude(url, title, area):
    prompt = f"""以下のページが神奈川県{area}の補助金・助成金・支援金のページかどうか判断してください。

URL: {url}
ページタイトルまたは内容: {title}

判断基準：
- 個人または事業者が申請できる補助金・助成金・支援金・給付金のページ → YES
- 制度の一覧ページ → YES  
- 申請受付終了・廃止済み → NO
- 補助金と無関係 → NO

以下のJSON形式のみで回答してください（他の文章は不要）：
{{"is_subsidy": true/false, "title": "補助金の正式名称", "category": "事業者向け/子育て・教育/住まい・住宅/介護・福祉のいずれか", "target": "個人/事業者"}}"""

    data = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 200,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "x-api-key": CLAUDE_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            result = json.loads(res.read())
            text = result["content"][0]["text"].strip()
            return json.loads(text)
    except:
        return None

def add_to_notion(title, area, category, target, url):
    props = {
        "名前": {"title": [{"text": {"content": title}}]},
        "対象": {"select": {"name": target}},
        "カテゴリ": {"select": {"name": category}},
        "市区町村": {"rich_text": [{"text": {"content": area}}]},
        "公式URL": {"url": url}
    }
    data = json.dumps({"parent": {"database_id": DB_ID}, "properties": props}).encode()
    req = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=data,
        headers=headers_notion,
        method="POST"
    )
    urllib.request.urlopen(req)

# メイン処理
existing_urls = get_existing_urls()
print(f"既存URL数: {len(existing_urls)}")

added = 0
for target in TARGETS:
    print(f"\n{target['area']}を巡回中...")
    html = fetch_page(target["url"])
    if not html:
        continue
    
    links = extract_links(html, target["url"])
    new_links = [l for l in links if l not in existing_urls and target["area"].split("市")[0] in l or "kanagawa" in l]
    new_links = list(set(new_links))[:10]  # 最大10件
    
    for link in new_links:
        result = ask_claude(link, link, target["area"])
        if result and result.get("is_subsidy"):
            try:
                add_to_notion(
                    result["title"],
                    target["area"],
                    result["category"],
                    result["target"],
                    link
                )
                print(f"✓ 追加: {result['title'][:40]}")
                added += 1
            except Exception as e:
                print(f"✗ 登録失敗: {e}")

print(f"\n新規追加: {added}件")
