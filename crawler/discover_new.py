import urllib.request, urllib.parse, json, os, re

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = os.environ["NOTION_DB_ID"]
CLAUDE_KEY = os.environ["CLAUDE_API_KEY"]

headers_notion = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 各自治体の補助金カテゴリページ（実在確認済み）
TARGETS = [
    {"area": "横浜市", "url": "https://www.city.yokohama.lg.jp/kurashi/sumai-kurashi/jutaku/sien/"},
    {"area": "横浜市", "url": "https://www.city.yokohama.lg.jp/business/kigyoshien/keieishien/"},
    {"area": "川崎市", "url": "https://www.city.kawasaki.jp/280/category/30-0-0-0-0-0-0-0-0-0.html"},
    {"area": "鎌倉市", "url": "https://www.city.kamakura.kanagawa.jp/kankyo/saiseihojyo.html"},
    {"area": "鎌倉市", "url": "https://www.city.kamakura.kanagawa.jp/kosodate/"},
    {"area": "藤沢市", "url": "https://www.city.fujisawa.kanagawa.jp/kodomo-se/teate_kyufu.html"},
    {"area": "横須賀市", "url": "https://www.city.yokosuka.kanagawa.jp/sangyo/keizai/shinko/index.html"},
    {"area": "平塚市", "url": "https://www.city.hiratsuka.kanagawa.jp/sangyo/page33_00038.html"},
    {"area": "相模原市", "url": "https://www.city.sagamihara.kanagawa.jp/kurashi/1026489/sumai/1026513/index.html"},
    {"area": "厚木市", "url": "https://www.city.atsugi.kanagawa.jp/kosodate_kyoiku/teate_josei/index.html"},
    {"area": "茅ヶ崎市", "url": "https://www.city.chigasaki.kanagawa.jp/kosodate/1024750/index.html"},
    {"area": "大和市", "url": "https://www.city.yamato.lg.jp/gyosei/soshik/40/sangyo/kigyoushien/hojokintou/4242.html"},
    {"area": "三浦市", "url": "https://www.city.miura.kanagawa.jp/shigoto_sangyo_machizukuri/sangyoshinko/6/shoukou2/index.html"},
    {"area": "逗子市", "url": "https://www.city.zushi.kanagawa.jp/kurashi/gomirecycle/1002120/index.html"},
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
    parsed_base = urllib.parse.urlparse(base_url)
    pattern = r'href=["\']([^"\'#?]+)["\']'
    for match in re.finditer(pattern, html):
        href = match.group(1)
        if href.startswith("http"):
            link = href
        elif href.startswith("/"):
            link = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
        else:
            continue
        # 同じドメインのページのみ
        if parsed_base.netloc in link and link not in links:
            links.append(link)
    return links

def ask_claude(url, area):
    prompt = f"""URLを見て、これが{area}の個人・事業者向け補助金・助成金・支援金・給付金のページかどうか判断してください。

URL: {url}

判断基準：
- 補助金・助成金・支援金・給付金・奨学金のページ → YES
- 申請・手続きページ → YES
- トップページ・お知らせ・採用・議会 → NO

JSON形式のみで回答（他の文章不要）：
{{"is_subsidy": true/false, "title": "制度名（わからなければURLから推測）", "category": "事業者向け/子育て・教育/住まい・住宅/介護・福祉のいずれか", "target": "個人/事業者"}}"""

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
            text = re.search(r'\{.*\}', text, re.DOTALL).group()
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
    print(f"\n{target['area']} {target['url'][-30:]}を巡回中...")
    html = fetch_page(target["url"])
    if not html:
        print("取得失敗")
        continue

    links = extract_links(html, target["url"])
    new_links = [l for l in links if l not in existing_urls]
    new_links = list(set(new_links))[:5]  # 各ページ最大5件
    print(f"新規リンク候補: {len(new_links)}件")

    for link in new_links:
        result = ask_claude(link, target["area"])
        if result and result.get("is_subsidy"):
            try:
                add_to_notion(result["title"], target["area"], result["category"], result["target"], link)
                print(f"✓ 追加: {result['title'][:40]}")
                added += 1
            except Exception as e:
                print(f"✗ 登録失敗: {e}")

print(f"\n新規追加: {added}件")
