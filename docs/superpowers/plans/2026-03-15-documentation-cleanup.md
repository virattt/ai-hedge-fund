# Documentation Cleanup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up project documentation from 40+ files to 9 essential user-facing guides (7 docs + 2 scripts)

**Architecture:** Delete redundant development docs, consolidate related content into retained guides, preserve all user-critical information

**Tech Stack:** Git, Markdown, Bash

---

## Chunk 1: Preparation and Content Consolidation

### Task 1: Create Backup Branch

**Files:**
- None (git operations only)

- [ ] **Step 1: Check git status**

Run: `git status`
Expected: Clean working directory or known uncommitted changes

- [ ] **Step 2: Create and checkout cleanup branch**

```bash
git checkout -b docs-cleanup
```

Expected: `Switched to a new branch 'docs-cleanup'`

- [ ] **Step 3: Verify branch**

Run: `git branch`
Expected: `* docs-cleanup` (asterisk indicates current branch)

- [ ] **Step 4: Commit current state as backup**

```bash
git add -A
git commit -m "chore: backup before documentation cleanup"
```

Expected: Commit created with all current changes

---

### Task 2: Extract Content from README_DATA_SOURCES.md

**Files:**
- Read: `README_DATA_SOURCES.md`
- Modify: `TROUBLESHOOTING.md` (will update in Task 3)

- [ ] **Step 1: Read README_DATA_SOURCES.md**

Run: `cat README_DATA_SOURCES.md`

Extract these sections:
1. Data source architecture diagram
2. Ticker format reference (US/CN/HK examples)
3. Data source status table

- [ ] **Step 2: Note content for consolidation**

Create temporary notes file:
```bash
cat > /tmp/consolidation-notes.md << 'EOF'
# Content to Add to TROUBLESHOOTING.md

## From README_DATA_SOURCES.md:

### Data Source Architecture
[Copy architecture diagram section]

### Ticker Format Reference
```
US: AAPL, MSFT
CN: 000001, 600000.SH
HK: 0700.HK
```

### Data Source Status
[Copy status table]
EOF
```

- [ ] **Step 3: Verify notes created**

Run: `cat /tmp/consolidation-notes.md`
Expected: File contains extracted content

---

### Task 3: Update TROUBLESHOOTING.md with Consolidated Content

**Files:**
- Modify: `TROUBLESHOOTING.md`
- Read: `/tmp/consolidation-notes.md`, `docs/DATA_SOURCE_RATE_LIMITING.md`, `docs/MULTI_SOURCE_GUIDE.md`

- [ ] **Step 1: Read current TROUBLESHOOTING.md**

Run: `cat TROUBLESHOOTING.md | head -50`

Identify insertion points for new sections

- [ ] **Step 2: Add Data Source Architecture section**

Add after the main header, before existing content:

```markdown
## 📊 Data Source Architecture

### Current Data Sources

| Data Source | Markets | Status | Rate Limiting | Use Case |
|-------------|---------|--------|---------------|----------|
| **Financial Datasets API** | US | ✅ Stable | API Key | Production (US stocks) |
| **Tushare Pro** | CN | ✅ Stable | Token auth | Production (CN stocks) |
| **AKShare** | CN, HK | ⚠️ Rate limited | Anti-crawler | Testing only |
| **YFinance** | Global | ⚠️ Rate limited | 429 errors | Backup only |

### Architecture Layers

```
MarketRouter (Auto-routing by ticker format)
    ↓
Market Adapters (CN/HK/US/Commodity)
    ↓
Data Sources (Tushare/AKShare/YFinance/FinancialDatasets)
    ↓
Validation & Caching
```

## 🎫 Ticker Format Reference

### US Stocks
```
AAPL        ✅ Apple
MSFT        ✅ Microsoft
GOOGL       ✅ Google
```

### CN A-Shares
```
000001      ✅ 6-digit (Ping An Bank - Shenzhen)
000001.SZ   ✅ Full format
600000      ✅ 6-digit (Pudong Bank - Shanghai)
600000.SH   ✅ Full format
```

### HK Stocks
```
0700.HK     ✅ Tencent
00700       ✅ Tencent (short)
9988.HK     ✅ Alibaba
```

---
```

- [ ] **Step 3: Commit consolidation changes**

```bash
git add TROUBLESHOOTING.md
git commit -m "docs: consolidate data source architecture into TROUBLESHOOTING"
```

---

### Task 4: Update README.md with Data Source Configuration

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find insertion point in README.md**

Run: `grep -n "## " README.md | head -20`

Find appropriate section after installation/setup

- [ ] **Step 2: Add Data Source Configuration section**

Insert after the setup section:

```markdown
## 💾 Data Source Configuration

### Quick Start

- **US Stocks**: Works out of the box with Financial Datasets API
- **CN/HK Stocks**: Requires Tushare Pro (recommended for stability)
  - **Quick setup**: `./setup_tushare.sh`
  - **Detailed guide**: [docs/TUSHARE_SETUP.md](docs/TUSHARE_SETUP.md)
  - **Register**: https://tushare.pro/register (free)

### Testing Data Sources

Verify your data source configuration:

```bash
poetry run python test_data_sources.py
```

Expected output:
```
✅ US Stocks    - PASS
✅ CN Stocks    - PASS (if Tushare configured)
✅ Market Router - PASS
```

### Troubleshooting

If you encounter data source issues, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
```

- [ ] **Step 3: Commit README changes**

```bash
git add README.md
git commit -m "docs: add data source configuration section to README"
```

---

## Chunk 2: File Deletion - Root Directory

### Task 5: Delete Root Directory Markdown Files

**Files:**
- Delete: Multiple markdown files in root directory

- [ ] **Step 1: List files to delete**

```bash
ls -1 *.md | grep -v -E "^(README|CLAUDE|TROUBLESHOOTING|CHANGELOG)\.md$"
```

Expected: Shows all markdown files except the 4 retained ones

- [ ] **Step 2: Delete Chinese-named documents**

```bash
rm -f 使用指南.md 快速参考.md 商品适配器实现总结.md 商品适配器快速参考.md API集成快速参考.md 项目深度对比分析.md
```

- [ ] **Step 3: Delete duplicate and summary documents**

```bash
rm -f README_CN.md README_DATA_SOURCES.md TUSHARE_QUICKSTART.md CONFIGURATION_SUMMARY.md DOCUMENTATION_SUMMARY.md
```

- [ ] **Step 4: Delete development documents**

```bash
rm -f FINAL_REPORT.md IMPLEMENTATION_SUMMARY.md IMPROVEMENTS_SUMMARY.md PROGRESS.md ARCHITECTURE_ANALYSIS.md ARCHITECTURE_COMPARISON.md CACHE_ENHANCEMENT_SUMMARY.md
```

- [ ] **Step 5: Verify only 4 markdown files remain in root**

Run: `ls -1 *.md`

Expected output:
```
CHANGELOG.md
CLAUDE.md
README.md
TROUBLESHOOTING.md
```

- [ ] **Step 6: Commit deletions**

```bash
git add -A
git commit -m "docs: remove redundant root directory documentation"
```

---

### Task 6: Delete Test Scripts

**Files:**
- Delete: `test_commodity_integration.py`, `test_rate_limit.py`, `verify_cache_enhancement.py`

- [ ] **Step 1: List test scripts in root**

```bash
ls -1 *.py
```

- [ ] **Step 2: Delete feature-specific test scripts**

```bash
rm -f test_commodity_integration.py test_rate_limit.py verify_cache_enhancement.py
```

- [ ] **Step 3: Verify only test_data_sources.py remains**

Run: `ls -1 *.py`

Expected: `test_data_sources.py` (and possibly src/ files, which is fine)

- [ ] **Step 4: Verify test_data_sources.py still works**

Run: `poetry run python test_data_sources.py`

Expected: Script runs and shows test results (may fail on data sources but script itself works)

- [ ] **Step 5: Commit deletions**

```bash
git add -A
git commit -m "docs: remove feature-specific test scripts"
```

---

### Task 7: Verify Root Directory Scripts

**Files:**
- Verify: `setup_tushare.sh`, `test_data_sources.py`

- [ ] **Step 1: List all scripts in root**

```bash
ls -1 *.sh *.py 2>/dev/null | grep -v "^src/"
```

Expected: Only `setup_tushare.sh` and `test_data_sources.py`

- [ ] **Step 2: Verify setup_tushare.sh is executable**

Run: `ls -l setup_tushare.sh`

Expected: `-rwxr-xr-x` (executable bit set)

If not executable:
```bash
chmod +x setup_tushare.sh
```

- [ ] **Step 3: Test setup_tushare.sh help**

Run: `./setup_tushare.sh --help || ./setup_tushare.sh -h || echo "No help flag, script is interactive"`

Expected: Help text or confirmation script exists and is executable

- [ ] **Step 4: Commit any permission changes**

```bash
git add setup_tushare.sh
git commit -m "chore: ensure setup script is executable" || echo "No changes to commit"
```

---

## Chunk 3: File Deletion - docs/ Directory

### Task 8: Delete docs/ Development Documents

**Files:**
- Delete: Multiple files in `docs/` directory

- [ ] **Step 1: List files to delete**

```bash
ls -1 docs/*.md | grep -v -E "(TUSHARE_SETUP|ANTI_RATE_LIMIT|testing_guide)\.md$"
```

Expected: Shows all docs/*.md files except the 3 retained ones

- [ ] **Step 2: Delete summary and duplicate documents**

```bash
cd docs
rm -f DATA_SOURCE_RATE_LIMITING.md ANTI_RATE_LIMIT_SUMMARY.md EXECUTION_SUMMARY.md LOG_ENHANCEMENT.md
```

- [ ] **Step 3: Delete monitoring and guide documents**

```bash
rm -f MONITORING_AND_CONFIG.md MULTI_SOURCE_GUIDE.md data-source-analysis.md test_quick_reference.md
```

- [ ] **Step 4: Delete implementation documents**

```bash
rm -f implementation-plan.md implementation-report.md enhanced-features-guide.md enhanced-features-guide-template.md
```

- [ ] **Step 5: Delete task summaries and reports**

```bash
rm -f task7_api_integration_summary.md task8_completion_summary.md e2e_test_report.md
```

- [ ] **Step 6: Return to root and verify only 3 docs remain**

```bash
cd ..
ls -1 docs/*.md
```

Expected output:
```
docs/ANTI_RATE_LIMIT.md
docs/TUSHARE_SETUP.md
docs/testing_guide.md
```

- [ ] **Step 7: Commit deletions**

```bash
git add -A
git commit -m "docs: remove development documents from docs/ directory"
```

---

### Task 9: Delete superpowers/ Development Documents

**Files:**
- Delete: `docs/superpowers/plans/2026-03-14-*.md`, `docs/superpowers/specs/2026-03-14-*.md`

- [ ] **Step 1: List superpowers documents**

```bash
find docs/superpowers -name "*.md" -type f
```

- [ ] **Step 2: Delete completed plan and spec from 2026-03-14**

```bash
rm -f docs/superpowers/plans/2026-03-14-多市场数据源层实现.md
rm -f docs/superpowers/specs/2026-03-14-多市场支持与用户体验增强设计.md
```

- [ ] **Step 3: Delete this cleanup design document**

```bash
rm -f docs/superpowers/specs/2026-03-15-documentation-cleanup-design.md
```

- [ ] **Step 4: Delete this cleanup plan document**

```bash
rm -f docs/superpowers/plans/2026-03-15-documentation-cleanup.md
```

- [ ] **Step 5: Verify superpowers/ is empty or only has .gitkeep**

```bash
find docs/superpowers -name "*.md" -type f
```

Expected: No output (or only .gitkeep files)

- [ ] **Step 6: Commit deletions**

```bash
git add -A
git commit -m "docs: remove completed superpowers development documents"
```

---

## Chunk 4: Verification and Final Commit

### Task 10: Verify Documentation Structure

**Files:**
- Verify: All retained documentation files

- [ ] **Step 1: Count markdown files in root**

```bash
ls -1 *.md | wc -l
```

Expected: `4` (README.md, CLAUDE.md, TROUBLESHOOTING.md, CHANGELOG.md)

- [ ] **Step 2: Count markdown files in docs/**

```bash
ls -1 docs/*.md 2>/dev/null | wc -l
```

Expected: `3` (TUSHARE_SETUP.md, ANTI_RATE_LIMIT.md, testing_guide.md)

- [ ] **Step 3: Count scripts in root**

```bash
ls -1 *.py *.sh 2>/dev/null | grep -v "^src/" | wc -l
```

Expected: `2` (test_data_sources.py, setup_tushare.sh)

- [ ] **Step 4: Verify total is 9 files**

```bash
echo "Total files: $(($(ls -1 *.md | wc -l) + $(ls -1 docs/*.md 2>/dev/null | wc -l) + $(ls -1 *.py *.sh 2>/dev/null | grep -v "^src/" | wc -l)))"
```

Expected: `Total files: 9`

---

### Task 11: Verify Internal Links

**Files:**
- Verify: All markdown files

- [ ] **Step 1: Extract all markdown links**

```bash
grep -r "\[.*\](.*\.md)" *.md docs/*.md 2>/dev/null | grep -v "http" | cut -d']' -f2 | sed 's/[()]//g' | sort -u > /tmp/doc-links.txt
```

- [ ] **Step 2: Check each link exists**

```bash
while read link; do
  if [ ! -f "$link" ]; then
    echo "❌ Broken link: $link"
  fi
done < /tmp/doc-links.txt
```

Expected: No output (all links valid) or only external links

- [ ] **Step 3: If broken links found, fix them**

For each broken link, either:
- Update the link to point to correct file
- Remove the link if target was intentionally deleted

Example fix:
```bash
# If link points to deleted file, update it
sed -i 's|docs/DATA_SOURCE_RATE_LIMITING.md|TROUBLESHOOTING.md#data-source-issues|g' TROUBLESHOOTING.md
```

- [ ] **Step 4: Commit any link fixes**

```bash
git add -A
git commit -m "docs: fix broken internal links" || echo "No broken links to fix"
```

---

### Task 12: Test Retained Scripts

**Files:**
- Test: `test_data_sources.py`, `setup_tushare.sh`

- [ ] **Step 1: Test data source test script**

Run: `poetry run python test_data_sources.py`

Expected: Script runs to completion (tests may fail due to rate limiting, but script itself should work)

Verify output includes:
- Test headers
- Test results (✅ or ❌)
- Summary section

- [ ] **Step 2: Test Tushare setup script exists and is executable**

Run: `./setup_tushare.sh --version 2>&1 | head -5 || echo "Script is interactive or has no --version flag"`

Expected: Script executes (may show help or interactive prompt)

- [ ] **Step 3: Verify scripts are in expected state**

```bash
ls -lh test_data_sources.py setup_tushare.sh
```

Expected: Both files exist and setup_tushare.sh is executable

---

### Task 13: Final Documentation Review

**Files:**
- Review: All retained markdown files

- [ ] **Step 1: Review README.md**

Run: `head -100 README.md`

Verify it contains:
- Project description
- Installation instructions
- Data source configuration section (newly added)
- Usage examples

- [ ] **Step 2: Review TROUBLESHOOTING.md**

Run: `head -100 TROUBLESHOOTING.md`

Verify it contains:
- Data source architecture (newly added)
- Ticker format reference (newly added)
- Troubleshooting sections
- Solutions

- [ ] **Step 3: Review docs/TUSHARE_SETUP.md**

Run: `head -50 docs/TUSHARE_SETUP.md`

Verify it contains:
- Registration instructions
- Token configuration steps
- Quick start section

- [ ] **Step 4: Review docs/ANTI_RATE_LIMIT.md**

Run: `head -50 docs/ANTI_RATE_LIMIT.md`

Verify it contains:
- Rate limiting mechanisms
- Configuration options

- [ ] **Step 5: Review docs/testing_guide.md**

Run: `head -50 docs/testing_guide.md`

Verify it contains:
- Test execution instructions
- Test structure information

---

### Task 14: Create Final Commit

**Files:**
- All changes

- [ ] **Step 1: Review all changes**

```bash
git status
git log --oneline -10
```

Verify all commits are present and descriptive

- [ ] **Step 2: Create summary of changes**

```bash
cat > /tmp/cleanup-summary.txt << 'EOF'
Documentation Cleanup Summary

Deleted:
- 14 root directory markdown files (duplicates, summaries, dev docs)
- 15 docs/ directory markdown files (dev docs, reports)
- 4 superpowers/ markdown files (completed plans/specs)
- 3 test scripts (feature-specific)

Retained:
- 4 root markdown files (README, CLAUDE, TROUBLESHOOTING, CHANGELOG)
- 3 docs/ markdown files (TUSHARE_SETUP, ANTI_RATE_LIMIT, testing_guide)
- 2 scripts (test_data_sources.py, setup_tushare.sh)

Updated:
- TROUBLESHOOTING.md: Added data source architecture and ticker formats
- README.md: Added data source configuration section

Result: 40+ files reduced to 9 essential files
EOF

cat /tmp/cleanup-summary.txt
```

- [ ] **Step 3: Verify no uncommitted changes**

Run: `git status`

Expected: `nothing to commit, working tree clean`

- [ ] **Step 4: View final file structure**

```bash
echo "=== Root Documentation ==="
ls -1 *.md
echo ""
echo "=== docs/ Documentation ==="
ls -1 docs/*.md
echo ""
echo "=== Root Scripts ==="
ls -1 *.py *.sh 2>/dev/null | grep -v "^src/"
```

Expected: Clean list of 9 files total

- [ ] **Step 5: Tag the cleanup completion**

```bash
git tag -a docs-cleanup-complete -m "Documentation cleanup: 40+ files → 9 essential files"
```

---

### Task 15: Merge to Main Branch

**Files:**
- None (git operations only)

- [ ] **Step 1: Switch to main branch**

```bash
git checkout main
```

Expected: `Switched to branch 'main'`

- [ ] **Step 2: Merge cleanup branch**

```bash
git merge docs-cleanup --no-ff -m "docs: cleanup and consolidate documentation

- Reduced 40+ files to 9 essential user-facing guides
- Deleted development docs, summaries, and duplicates
- Consolidated data source info into TROUBLESHOOTING.md
- Added data source config section to README.md
- Retained: 4 root docs + 3 docs/ docs + 2 scripts"
```

Expected: Merge successful

- [ ] **Step 3: Verify merge**

```bash
git log --oneline -5
ls -1 *.md | wc -l
ls -1 docs/*.md | wc -l
```

Expected:
- Merge commit at top of log
- 4 markdown files in root
- 3 markdown files in docs/

- [ ] **Step 4: Delete cleanup branch**

```bash
git branch -d docs-cleanup
```

Expected: `Deleted branch docs-cleanup`

- [ ] **Step 5: Final verification**

Run: `poetry run python test_data_sources.py`

Expected: Script runs successfully (tests may fail due to rate limiting, but script works)

---

## Success Criteria

After completing all tasks:

- ✅ Only 4 markdown files in root directory
- ✅ Only 3 markdown files in docs/ directory
- ✅ Only 2 scripts in root directory (test_data_sources.py, setup_tushare.sh)
- ✅ TROUBLESHOOTING.md contains consolidated data source information
- ✅ README.md contains data source configuration section
- ✅ No broken internal links
- ✅ test_data_sources.py runs successfully
- ✅ All changes committed to main branch
- ✅ Cleanup branch deleted

Total: 9 essential files (7 docs + 2 scripts)
