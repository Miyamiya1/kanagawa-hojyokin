export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const NOTION_TOKEN = process.env.NOTION_TOKEN;
  const DB_ID = process.env.NOTION_DB_ID;

  let all = [];
  let cursor = undefined;

  while (true) {
    const body = { page_size: 100 };
    if (cursor) body.start_cursor = cursor;

    const response = await fetch(`https://api.notion.com/v1/databases/${DB_ID}/query`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${NOTION_TOKEN}`,
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    all = all.concat(data.results);

    if (!data.has_more) break;
    cursor = data.next_cursor;
  }

  const subsidies = all.map(page => ({
    id: page.id,
    title: page.properties['名前']?.title[0]?.text?.content || '',
    target: page.properties['対象']?.select?.name || '',
    category: page.properties['カテゴリ']?.select?.name || '',
    area: page.properties['市区町村']?.rich_text[0]?.text?.content || '',
    summary: page.properties['概要']?.rich_text[0]?.text?.content || '',
    url: page.properties['公式URL']?.url || '',
  }));

  res.json(subsidies);
}
