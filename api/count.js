const NOTION_TOKEN = process.env.NOTION_TOKEN;
const COUNT_PAGE_ID = process.env.COUNT_PAGE_ID;

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');

  const pageRes = await fetch(`https://api.notion.com/v1/pages/${COUNT_PAGE_ID}`, {
    headers: {
      'Authorization': `Bearer ${NOTION_TOKEN}`,
      'Notion-Version': '2022-06-28',
    }
  });
  const page = await pageRes.json();
  const current = page.properties?.['カウント']?.number || 0;

  if (req.method === 'POST') {
    const newCount = current + 1;
    await fetch(`https://api.notion.com/v1/pages/${COUNT_PAGE_ID}`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${NOTION_TOKEN}`,
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        properties: { 'カウント': { number: newCount } }
      })
    });
    res.json({ count: newCount });
  } else {
    res.json({ count: current });
  }
}
