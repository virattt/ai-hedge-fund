# Documentation Cleanup Design

**Date**: 2026-03-15
**Author**: Claude (Opus 4.6)
**Status**: Approved

## Overview

This design document outlines the cleanup and consolidation of project documentation to maintain only user-facing guides while removing development process documents, implementation summaries, and redundant files.

## Problem Statement

The project currently has approximately 40+ documentation files scattered across the root directory and `docs/` folder, including:
- Redundant documentation in multiple languages
- Development process documents (implementation summaries, progress reports)
- Temporary configuration summaries
- Duplicate quick reference guides
- Multiple testing scripts for specific features

This creates confusion for users and makes maintenance difficult.

## Goals

1. **Simplify documentation structure** - Keep only essential user-facing guides
2. **Remove development artifacts** - Delete implementation summaries, progress reports, and temporary docs
3. **Eliminate redundancy** - Remove duplicate content and consolidate related information
4. **Maintain usability** - Ensure users can still configure, troubleshoot, and test the system

## Design

### Retained Documentation Structure

```
ai-hedge-fund/
├── README.md                          # Main project documentation (English)
├── CLAUDE.md                          # Claude Code development guide
├── TROUBLESHOOTING.md                 # Consolidated troubleshooting guide
├── CHANGELOG.md                       # Version history
├── setup_tushare.sh                   # Tushare configuration script
├── test_data_sources.py               # Data source testing script
└── docs/
    ├── TUSHARE_SETUP.md              # Detailed Tushare configuration
    ├── ANTI_RATE_LIMIT.md            # Anti-rate-limiting mechanisms
    └── testing_guide.md              # Testing guide
```

**Total**: 7 documents + 2 scripts

### Files to Delete

#### Root Directory (14 files):
1. `README_CN.md` - Chinese README (duplicate)
2. `README_DATA_SOURCES.md` - Data sources guide (consolidated into TROUBLESHOOTING)
3. `TUSHARE_QUICKSTART.md` - Quick config (content in docs/TUSHARE_SETUP.md)
4. `CONFIGURATION_SUMMARY.md` - Configuration summary (temporary)
5. `DOCUMENTATION_SUMMARY.md` - Documentation summary (temporary)
6. `FINAL_REPORT.md` - Final report (development doc)
7. `IMPLEMENTATION_SUMMARY.md` - Implementation summary (development doc)
8. `IMPROVEMENTS_SUMMARY.md` - Improvements summary (development doc)
9. `PROGRESS.md` - Progress report (development doc)
10. `ARCHITECTURE_ANALYSIS.md` - Architecture analysis (development doc)
11. `ARCHITECTURE_COMPARISON.md` - Architecture comparison (development doc)
12. `CACHE_ENHANCEMENT_SUMMARY.md` - Cache enhancement summary (development doc)
13. All Chinese-named documents (`使用指南.md`, `快速参考.md`, etc.)
14. `API集成快速参考.md`, `商品适配器实现总结.md`, `商品适配器快速参考.md`, `项目深度对比分析.md`

#### docs/ Directory (15 files):
1. `docs/DATA_SOURCE_RATE_LIMITING.md` - Rate limiting details (consolidated)
2. `docs/ANTI_RATE_LIMIT_SUMMARY.md` - Anti-rate-limit summary (duplicate)
3. `docs/EXECUTION_SUMMARY.md` - Execution summary (development doc)
4. `docs/LOG_ENHANCEMENT.md` - Log enhancement (development doc)
5. `docs/MONITORING_AND_CONFIG.md` - Monitoring config (rarely used)
6. `docs/MULTI_SOURCE_GUIDE.md` - Multi-source guide (consolidated)
7. `docs/data-source-analysis.md` - Data source analysis (development doc)
8. `docs/implementation-plan.md` - Implementation plan (development doc)
9. `docs/implementation-report.md` - Implementation report (development doc)
10. `docs/enhanced-features-guide.md` - Features guide (development doc)
11. `docs/enhanced-features-guide-template.md` - Template (development doc)
12. `docs/task7_api_integration_summary.md` - Task summary (development doc)
13. `docs/task8_completion_summary.md` - Task summary (development doc)
14. `docs/e2e_test_report.md` - Test report (development doc)
15. `docs/test_quick_reference.md` - Test quick reference (consolidated)

#### Test Scripts (3 files):
1. `test_commodity_integration.py` - Commodity-specific test
2. `test_rate_limit.py` - Rate limit-specific test
3. `verify_cache_enhancement.py` - Cache verification script

**Total deletions**: ~35 files

### Documentation Updates

#### 1. TROUBLESHOOTING.md

**Consolidate content from**:
- `README_DATA_SOURCES.md` - Data source overview
- `docs/DATA_SOURCE_RATE_LIMITING.md` - Rate limiting details
- `docs/MULTI_SOURCE_GUIDE.md` - Multi-source usage

**Structure**:
```markdown
# Troubleshooting Guide

## Data Source Issues
- Rate limiting problems
- Connection failures
- Configuration errors

## Market-Specific Issues
- US stocks
- CN stocks (A-share)
- HK stocks

## Solutions
- Tushare integration
- Proxy configuration
- Cache tuning
```

#### 2. README.md

**Add data source configuration section**:
```markdown
## Data Source Configuration

### Quick Start
- **US Stocks**: Works out of the box
- **CN/HK Stocks**: Requires Tushare (recommended)
  - Quick setup: `./setup_tushare.sh`
  - Detailed guide: [docs/TUSHARE_SETUP.md](docs/TUSHARE_SETUP.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### Testing Data Sources
```bash
poetry run python test_data_sources.py
```
```

## Implementation Plan

### Phase 1: Backup
1. Create git branch: `docs-cleanup`
2. Commit current state as backup

### Phase 2: Delete Files
1. Delete root directory markdown files (except retained 4)
2. Delete docs/ directory files (except retained 3)
3. Delete test scripts (except test_data_sources.py)
4. Delete setup scripts (except setup_tushare.sh)

### Phase 3: Update Documentation
1. Update TROUBLESHOOTING.md with consolidated content
2. Update README.md with data source configuration section
3. Verify all internal links still work

### Phase 4: Commit and Verify
1. Review changes
2. Commit with descriptive message
3. Test that retained scripts still work
4. Verify documentation is complete and accessible

## Validation

### Success Criteria
- ✅ Only 7 markdown files in root + docs/
- ✅ Only 2 scripts in root
- ✅ All user-facing guides are accessible
- ✅ No broken internal links
- ✅ Test scripts run successfully

### Testing
```bash
# Verify retained scripts work
poetry run python test_data_sources.py
./setup_tushare.sh --help

# Check documentation links
grep -r "\[.*\](.*\.md)" *.md docs/*.md
```

## Risks and Mitigation

### Risk: Accidental deletion of important content
**Mitigation**: All changes in git branch, can be reverted

### Risk: Broken internal links
**Mitigation**: Verify all markdown links before final commit

### Risk: Missing user-critical information
**Mitigation**: Review each deleted file for unique content, consolidate into retained docs

## Future Maintenance

### Documentation Standards
1. **User guides only** - No development process docs in main branch
2. **Single source of truth** - No duplicate content
3. **English primary** - Chinese translations optional, in separate branch
4. **Clear structure** - README → specific guides → troubleshooting

### Adding New Documentation
- User guides: Add to `docs/`
- Development docs: Keep in branch or delete after completion
- Quick references: Consolidate into existing guides

## Conclusion

This cleanup will reduce documentation from 40+ files to 9 essential files (7 docs + 2 scripts), making the project more maintainable while preserving all user-critical information.
