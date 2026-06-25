#!/bin/bash
# Product Radar Daily Scan - Cron wrapper
# Runs scan + deploy, outputs summary for cron delivery
set -e
cd /home/lee/product-radar

# ScraperAPI fallback key (free: 5000 req/month)
# Register at https://dashboard.scraperapi.com/signup
export SCRAPER_API_KEY=""
if [ -f "/home/lee/.hermes/scraperapi_key.txt" ]; then
    export SCRAPER_API_KEY=$(cat "/home/lee/.hermes/scraperapi_key.txt" | tr -d '\n')
fi

# All detail goes to log file; cron only sees the one-line result
LOG="/home/lee/product-radar/logs/cron_$(date '+%Y%m%d_%H%M%S').log"
mkdir -p /home/lee/product-radar/logs
find /home/lee/product-radar/logs -name "cron_*.log" -mtime +7 -delete 2>/dev/null

{
echo "🔍 选品雷达自动扫描 | $(date '+%Y-%m-%d %H:%M')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# V3: Festival deadline check (inject keywords before scan)
echo ""
echo "📅 检查节日截止日..."
python3 run_festival_check.py 2>&1 || echo "  ⚠️ 节日检查失败（不影响扫描）"

# Run scan (timeout: 10 min) - includes build_platform internally
timeout 600 python3 run_scan_v2.py 2>/dev/null || { echo "❌ 扫描超时或失败"; exit 1; }

# Get latest data file
LATEST=$(ls -t data/channels/*.json 2>/dev/null | grep -v rejected | grep -v trends | head -1)
if [ -z "$LATEST" ]; then
    echo "❌ 扫描失败：无数据文件"
    exit 1
fi

# Extract summary
PRODUCTS=$(python3 -c "import json; d=json.load(open('$LATEST')); print(len(d.get('products',[])))")
SCANNED=$(python3 -c "import json; d=json.load(open('$LATEST')); print(d.get('stats',{}).get('total_scanned',0))")
DATE=$(python3 -c "import json; d=json.load(open('$LATEST')); print(d.get('scan_date',''))")
TIME=$(python3 -c "import json; d=json.load(open('$LATEST')); print(d.get('scan_time',''))")

echo ""
echo "📊 扫描结果：${SCANNED}个产品 → ${PRODUCTS}个通过筛选"
echo "📅 扫描时间：${DATE} ${TIME}"

# Top 3 products
echo ""
echo "🏆 Top 3 推荐："
python3 -c "
import json
d = json.load(open('$LATEST'))
for i, p in enumerate(d.get('products',[])[:3], 1):
    sig = p.get('signal_label', '?')
    sd = p.get('sd_label', '')
    print(f'  {i}. {p[\"name\"][:50]}')
    print(f'     £{p[\"price\"]} | 利润{p[\"profit_margin\"]*100:.0f}% | 评分{p[\"score\"]} | {sig} {sd}')
"

# 飞书推送 (timeout: 2 min)
echo ""
echo "📨 推送到飞书..."
timeout 120 python3 feishu_push.py 2>&1 || echo "  ⚠️ 飞书推送失败（不影响扫描）"

# Deploy to GitHub (timeout: 1 min total)
echo ""
echo "📦 部署到 GitHub Pages..."
timeout 30 git add data/ output/ status.json output/*.json -f 2>/dev/null
git diff --cached --quiet && echo "  无变更" && exit 0
timeout 15 git commit -m "auto-scan $(date -u '+%Y-%m-%d %H:%M')" 2>/dev/null
timeout 30 git pull --rebase 2>/dev/null || true

# Push (token already embedded in remote URL)
timeout 30 git pull --rebase origin main 2>&1 || true
timeout 30 git push origin main 2>&1
if [ $? -eq 0 ]; then
    echo "  ✅ 已部署：https://liyuhong168.github.io/product-radar/v2.html"
else
    echo "  ❌ Push失败，请检查"
    exit 1
fi

} > "$LOG" 2>&1 || {
    # On failure, output error for cron alert
    echo "❌ 选品雷达扫描失败 | $(date '+%Y-%m-%d %H:%M')"
    tail -3 "$LOG"
    exit 1
}

# On success, one-line summary for cron delivery
PRODUCTS=$(python3 -c "import json; d=json.load(open('$(ls -t data/channels/*.json 2>/dev/null | grep -v rejected | grep -v trends | head -1)')); print(len(d.get('products',[])))")
echo "✅ 选品雷达扫描完成 | $(date '+%Y-%m-%d %H:%M') | ${PRODUCTS}个产品通过筛选 → 已推送飞书+部署GitHub"
