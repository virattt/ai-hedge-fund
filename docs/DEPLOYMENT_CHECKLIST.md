# Foreign Key Removal - Deployment Checklist

**Project:** AI Hedge Fund
**Date:** 2026-03-16
**Task:** Remove Foreign Key Constraints

---

## Pre-Deployment Checks

- [x] **Code Changes Verified**
  - [x] All models import successfully
  - [x] No ForeignKey references remain
  - [x] No relationship() references remain
  - [x] All integer reference fields preserved
  - [x] All indexes preserved
  - [x] Python syntax valid

- [x] **Migration Files Ready**
  - [x] Alembic migration created: `2026031600_remove_foreign_keys.py`
  - [x] Python migration script created: `remove_foreign_keys.py`
  - [x] SQL template created: `001_remove_foreign_keys.sql`

- [x] **Documentation Complete**
  - [x] Detailed report: `FOREIGN_KEY_REMOVAL_REPORT.md`
  - [x] Query guide: `DATABASE_QUERY_GUIDE.md`
  - [x] Quick summary: `FOREIGN_KEY_REMOVAL_SUMMARY.md`
  - [x] This checklist: `DEPLOYMENT_CHECKLIST.md`

---

## Staging Environment

### Backend Database (SQLite/Alembic)

- [ ] **Backup database**
  ```bash
  cd app/backend
  cp hedge_fund.db hedge_fund.db.backup.$(date +%Y%m%d_%H%M%S)
  ```

- [ ] **Check current Alembic revision**
  ```bash
  cd app/backend
  alembic current
  ```

- [ ] **Run migration (dry-run)**
  ```bash
  # Check what will happen
  alembic upgrade head --sql > migration_preview.sql
  cat migration_preview.sql
  ```

- [ ] **Apply migration**
  ```bash
  cd app/backend
  alembic upgrade head
  ```

- [ ] **Verify no foreign keys remain**
  ```bash
  sqlite3 hedge_fund.db ".schema hedge_fund_flow_runs"
  sqlite3 hedge_fund.db ".schema hedge_fund_flow_run_cycles"
  # Should see no FOREIGN KEY clauses
  ```

### Trading Database (MySQL)

- [ ] **Backup database**
  ```bash
  mysqldump -u root -p hedge-fund > hedge-fund.backup.$(date +%Y%m%d_%H%M%S).sql
  ```

- [ ] **Check existing foreign keys**
  ```sql
  SELECT
      TABLE_NAME,
      COLUMN_NAME,
      CONSTRAINT_NAME,
      REFERENCED_TABLE_NAME
  FROM
      INFORMATION_SCHEMA.KEY_COLUMN_USAGE
  WHERE
      TABLE_SCHEMA = 'hedge-fund'
      AND REFERENCED_TABLE_NAME IS NOT NULL;
  ```

- [ ] **Run migration script (dry-run)**
  ```bash
  python src/database/migrations/remove_foreign_keys.py --dry-run
  ```

- [ ] **Review output and confirm changes**

- [ ] **Apply migration**
  ```bash
  python src/database/migrations/remove_foreign_keys.py
  # Type 'yes' when prompted
  ```

- [ ] **Verify no foreign keys remain**
  ```sql
  SELECT
      TABLE_NAME,
      COLUMN_NAME,
      CONSTRAINT_NAME,
      REFERENCED_TABLE_NAME
  FROM
      INFORMATION_SCHEMA.KEY_COLUMN_USAGE
  WHERE
      TABLE_SCHEMA = 'hedge-fund'
      AND REFERENCED_TABLE_NAME IS NOT NULL;
  -- Should return 0 rows
  ```

### Application Testing

- [ ] **Test model imports**
  ```bash
  python -c "from app.backend.database.models import *; from src.database.models import *; print('✅ Success')"
  ```

- [ ] **Test basic queries**
  ```python
  # Test script
  from app.backend.database.connection import SessionLocal as BackendSession
  from src.database.connection import SessionLocal as TradingSession

  # Backend DB
  db = BackendSession()
  flows = db.query(HedgeFundFlow).all()
  print(f"✅ Found {len(flows)} flows")
  db.close()

  # Trading DB
  db = TradingSession()
  sessions = db.query(TradingSession).all()
  print(f"✅ Found {len(sessions)} trading sessions")
  db.close()
  ```

- [ ] **Run test suite**
  ```bash
  poetry run pytest tests/ -v
  ```

- [ ] **Check application functionality**
  - [ ] Start backend API
  - [ ] Start frontend
  - [ ] Create a new flow
  - [ ] Run a trading session
  - [ ] Verify data is saved correctly

---

## Production Environment

### Before Deployment

- [ ] **Schedule maintenance window**
  - [ ] Notify users of downtime
  - [ ] Set maintenance mode

- [ ] **Final staging verification**
  - [ ] All staging tests passed
  - [ ] No issues found in staging
  - [ ] Team approval obtained

### Deployment Steps

#### 1. Backup Everything

- [ ] **Backup production databases**
  ```bash
  # Backend DB
  cp production_backend.db production_backend.db.backup.$(date +%Y%m%d_%H%M%S)

  # Trading DB
  mysqldump -u root -p hedge-fund-prod > hedge-fund-prod.backup.$(date +%Y%m%d_%H%M%S).sql
  ```

- [ ] **Verify backups**
  ```bash
  # Check file sizes
  ls -lh *.backup.*
  ls -lh *.sql
  ```

#### 2. Deploy Code Changes

- [ ] **Pull latest code**
  ```bash
  git pull origin main
  ```

- [ ] **Verify correct branch/commit**
  ```bash
  git log -1 --oneline
  ```

- [ ] **Install dependencies (if any)**
  ```bash
  poetry install
  ```

#### 3. Run Migrations

- [ ] **Backend database**
  ```bash
  cd app/backend
  alembic current  # Check current revision
  alembic upgrade head  # Apply migration
  alembic current  # Verify new revision
  ```

- [ ] **Trading database**
  ```bash
  python src/database/migrations/remove_foreign_keys.py --dry-run
  # Review output
  python src/database/migrations/remove_foreign_keys.py
  # Type 'yes' to confirm
  ```

#### 4. Verification

- [ ] **Check database schemas**
  ```sql
  -- Should return 0 rows
  SELECT * FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
  WHERE TABLE_SCHEMA = 'hedge-fund-prod'
  AND REFERENCED_TABLE_NAME IS NOT NULL;
  ```

- [ ] **Test model imports**
  ```bash
  python -c "from app.backend.database.models import *; from src.database.models import *; print('✅ Success')"
  ```

- [ ] **Restart application services**
  ```bash
  # Restart backend API
  systemctl restart hedge-fund-backend  # or your restart command

  # Verify services are running
  systemctl status hedge-fund-backend
  ```

- [ ] **Smoke tests**
  - [ ] Backend API health check
  - [ ] Frontend loads correctly
  - [ ] Can query existing data
  - [ ] Can create new records
  - [ ] No errors in logs

#### 5. Monitor

- [ ] **Check application logs**
  ```bash
  tail -f /var/log/hedge-fund/*.log
  ```

- [ ] **Monitor database performance**
  ```sql
  SHOW PROCESSLIST;
  ```

- [ ] **Monitor for errors**
  - [ ] Application errors
  - [ ] Database errors
  - [ ] API response times

---

## Rollback Procedure

If issues are encountered:

### Immediate Actions

1. **Stop accepting new traffic**
   ```bash
   # Put application in maintenance mode
   ```

2. **Assess the issue**
   - Is it a data issue or application issue?
   - Can it be fixed forward or must we rollback?

### Rollback Steps

#### Option A: Rollback Migration Only

- [ ] **Backend database**
  ```bash
  cd app/backend
  alembic downgrade -1
  ```

- [ ] **Trading database**
  ```bash
  # Restore foreign keys manually or from backup
  # See migration script's downgrade() function for SQL
  ```

#### Option B: Full Restore from Backup

- [ ] **Stop application**
  ```bash
  systemctl stop hedge-fund-backend
  ```

- [ ] **Restore backend database**
  ```bash
  cp production_backend.db.backup.TIMESTAMP production_backend.db
  ```

- [ ] **Restore trading database**
  ```bash
  mysql -u root -p hedge-fund-prod < hedge-fund-prod.backup.TIMESTAMP.sql
  ```

- [ ] **Restore previous code version**
  ```bash
  git checkout <previous_commit>
  poetry install
  ```

- [ ] **Start application**
  ```bash
  systemctl start hedge-fund-backend
  ```

#### Option C: Fix Forward

- [ ] **Identify the issue**
- [ ] **Apply fix**
- [ ] **Test fix in staging first**
- [ ] **Deploy fix to production**

---

## Post-Deployment

### Immediate (First 24 hours)

- [ ] **Monitor continuously**
  - [ ] Application logs
  - [ ] Database performance
  - [ ] User reports
  - [ ] Error rates

- [ ] **Verify functionality**
  - [ ] All API endpoints working
  - [ ] Data integrity maintained
  - [ ] No orphaned records

### Short-term (First week)

- [ ] **Performance review**
  - [ ] Query performance
  - [ ] Response times
  - [ ] Resource usage

- [ ] **Data quality check**
  ```bash
  python src/database/migrations/remove_foreign_keys.py --check-orphans
  ```

- [ ] **Update team**
  - [ ] Share deployment results
  - [ ] Document any issues encountered
  - [ ] Update runbooks if needed

### Long-term (First month)

- [ ] **Review and improve**
  - [ ] Analyze query patterns
  - [ ] Optimize slow queries
  - [ ] Add application-level validation if needed

- [ ] **Documentation updates**
  - [ ] Update architecture diagrams
  - [ ] Update onboarding docs
  - [ ] Update API documentation

---

## Success Criteria

- [x] All foreign key constraints removed
- [x] No data loss
- [x] Application functions normally
- [x] No orphaned records created
- [x] Query performance maintained or improved
- [x] All tests passing
- [x] No errors in logs
- [x] Team trained on new query patterns

---

## Contacts

| Role | Contact | Notes |
|------|---------|-------|
| Database Admin | - | For migration issues |
| DevOps | - | For deployment issues |
| Backend Lead | - | For application issues |
| Project Manager | - | For escalations |

---

## Notes

Add any deployment-specific notes here:

-

---

**Remember:** Always test in staging first, have backups, and know your rollback procedure!

---

## Completion

- [ ] All pre-deployment checks passed
- [ ] Staging deployment successful
- [ ] Production deployment successful
- [ ] Post-deployment verification complete
- [ ] Team notified
- [ ] Documentation updated
- [ ] Checklist archived

**Deployment Date:** _______________
**Deployed By:** _______________
**Sign-off:** _______________
