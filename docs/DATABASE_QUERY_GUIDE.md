# Database Query Guide (After Foreign Key Removal)

This guide provides examples of how to query related data now that foreign key constraints and SQLAlchemy relationships have been removed.

---

## Quick Reference

| Before (with relationships) | After (without relationships) |
|-----------------------------|------------------------------|
| `session.decisions` | Manual join or filter query |
| `decision.session` | Manual join or filter query |
| Automatic cascade delete | Manual cleanup required |

---

## Common Query Patterns

### 1. Get All Decisions for a Session

**Before (using relationships):**
```python
session = db.query(TradingSession).first()
decisions = session.decisions  # Uses relationship
```

**After (using filter):**
```python
session = db.query(TradingSession).first()
decisions = db.query(TradingDecision).filter(
    TradingDecision.session_id == session.id
).all()
```

**After (using explicit join):**
```python
results = db.query(TradingSession, TradingDecision).join(
    TradingDecision,
    TradingSession.id == TradingDecision.session_id
).filter(TradingSession.id == session_id).all()

# Extract data
for session, decision in results:
    print(f"Session: {session.id}, Decision: {decision.action}")
```

---

### 2. Get Session from a Decision

**Before (using back_populates):**
```python
decision = db.query(TradingDecision).first()
session = decision.session  # Uses relationship
```

**After (using filter):**
```python
decision = db.query(TradingDecision).first()
session = db.query(TradingSession).filter(
    TradingSession.id == decision.session_id
).first()
```

---

### 3. Get Multiple Related Records

**Before (using relationships):**
```python
session = db.query(TradingSession).first()
decisions = session.decisions
analyses = session.analyst_analyses
```

**After (using multiple queries):**
```python
session = db.query(TradingSession).first()

decisions = db.query(TradingDecision).filter(
    TradingDecision.session_id == session.id
).all()

analyses = db.query(AnalystAnalysis).filter(
    AnalystAnalysis.session_id == session.id
).all()
```

**After (using subqueryload pattern):**
```python
from sqlalchemy.orm import aliased

session = db.query(TradingSession).filter(
    TradingSession.id == session_id
).first()

# Load related data in single query with joins
decisions = db.query(TradingDecision).filter(
    TradingDecision.session_id == session_id
).all()

analyses = db.query(AnalystAnalysis).filter(
    AnalystAnalysis.session_id == session_id
).all()
```

---

### 4. Filter with Related Data

**Before (using relationship):**
```python
# Get sessions with at least one decision
sessions = db.query(TradingSession).join(
    TradingSession.decisions
).distinct().all()
```

**After (using explicit join):**
```python
sessions = db.query(TradingSession).join(
    TradingDecision,
    TradingSession.id == TradingDecision.session_id
).distinct().all()
```

---

### 5. Count Related Records

**Before (using relationship):**
```python
session = db.query(TradingSession).first()
count = len(session.decisions)
```

**After (using count query):**
```python
session = db.query(TradingSession).first()
count = db.query(TradingDecision).filter(
    TradingDecision.session_id == session.id
).count()
```

---

### 6. Delete with Cascade

**Before (automatic cascade):**
```python
# This would automatically delete related decisions and analyses
db.query(TradingSession).filter(
    TradingSession.id == session_id
).delete()
db.commit()
```

**After (manual cascade):**
```python
# Must manually delete related records first
db.query(TradingDecision).filter(
    TradingDecision.session_id == session_id
).delete()

db.query(AnalystAnalysis).filter(
    AnalystAnalysis.session_id == session_id
).delete()

db.query(MarketData).filter(
    MarketData.session_id == session_id
).delete()

db.query(PerformanceMetrics).filter(
    PerformanceMetrics.session_id == session_id
).delete()

# Finally delete the session
db.query(TradingSession).filter(
    TradingSession.id == session_id
).delete()

db.commit()
```

**Better approach with helper function:**
```python
def delete_session_cascade(db, session_id):
    """Delete a trading session and all related records."""
    try:
        # Delete in reverse dependency order
        db.query(TradingDecision).filter(
            TradingDecision.session_id == session_id
        ).delete()

        db.query(AnalystAnalysis).filter(
            AnalystAnalysis.session_id == session_id
        ).delete()

        db.query(MarketData).filter(
            MarketData.session_id == session_id
        ).delete()

        db.query(PerformanceMetrics).filter(
            PerformanceMetrics.session_id == session_id
        ).delete()

        db.query(TradingSession).filter(
            TradingSession.id == session_id
        ).delete()

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error deleting session: {e}")
        return False

# Usage
delete_session_cascade(db, session_id)
```

---

## Backend Database Queries

### Get Flow Run Details

**Before:**
```python
flow = db.query(HedgeFundFlow).first()
runs = flow.runs  # If relationship existed
```

**After:**
```python
flow = db.query(HedgeFundFlow).first()
runs = db.query(HedgeFundFlowRun).filter(
    HedgeFundFlowRun.flow_id == flow.id
).all()
```

### Get Cycles for a Run

**Before:**
```python
run = db.query(HedgeFundFlowRun).first()
cycles = run.cycles  # If relationship existed
```

**After:**
```python
run = db.query(HedgeFundFlowRun).first()
cycles = db.query(HedgeFundFlowRunCycle).filter(
    HedgeFundFlowRunCycle.flow_run_id == run.id
).order_by(HedgeFundFlowRunCycle.cycle_number).all()
```

---

## Best Practices

### 1. Create Helper Functions

Encapsulate common query patterns in reusable functions:

```python
def get_session_with_details(db, session_id):
    """Get a session with all related data."""
    session = db.query(TradingSession).filter(
        TradingSession.id == session_id
    ).first()

    if not session:
        return None

    return {
        'session': session,
        'decisions': db.query(TradingDecision).filter(
            TradingDecision.session_id == session_id
        ).all(),
        'analyses': db.query(AnalystAnalysis).filter(
            AnalystAnalysis.session_id == session_id
        ).all(),
        'metrics': db.query(PerformanceMetrics).filter(
            PerformanceMetrics.session_id == session_id
        ).first()
    }
```

### 2. Use Indexes

All `session_id`, `flow_id`, and `flow_run_id` fields retain their indexes for performance:

```python
# These queries are efficient due to indexes
decisions = db.query(TradingDecision).filter(
    TradingDecision.session_id == session_id  # Uses index
).all()
```

### 3. Batch Operations

When dealing with multiple records, use `in_()` for efficiency:

```python
session_ids = [1, 2, 3, 4, 5]

# Get all decisions for multiple sessions at once
decisions = db.query(TradingDecision).filter(
    TradingDecision.session_id.in_(session_ids)
).all()

# Group by session_id in Python
from collections import defaultdict
decisions_by_session = defaultdict(list)
for decision in decisions:
    decisions_by_session[decision.session_id].append(decision)
```

### 4. Validation Before Insert

Add application-level validation to ensure referential integrity:

```python
def create_trading_decision(db, session_id, **kwargs):
    """Create a trading decision with validation."""
    # Validate session exists
    session = db.query(TradingSession).filter(
        TradingSession.id == session_id
    ).first()

    if not session:
        raise ValueError(f"Session {session_id} does not exist")

    # Create decision
    decision = TradingDecision(
        session_id=session_id,
        **kwargs
    )
    db.add(decision)
    db.commit()
    return decision
```

### 5. Check for Orphans

Periodically check for orphaned records:

```python
def find_orphaned_decisions(db):
    """Find decisions with invalid session_id."""
    # Find all decision session_ids
    decision_session_ids = db.query(
        TradingDecision.session_id.distinct()
    ).all()

    # Find all valid session_ids
    valid_session_ids = db.query(TradingSession.id).all()
    valid_ids = {id[0] for id in valid_session_ids}

    # Find orphans
    orphans = [
        sid[0] for sid in decision_session_ids
        if sid[0] not in valid_ids
    ]

    return orphans
```

---

## Migration from Old Code

### Step 1: Find Relationship Usage
```bash
grep -r "\.decisions\|\.analyst_analyses\|\.session" src/
```

### Step 2: Replace with Explicit Queries
For each match, replace with the patterns shown above.

### Step 3: Test Thoroughly
- Unit tests for query functions
- Integration tests for data retrieval
- Performance tests for large datasets

---

## Performance Considerations

### Indexes Still Work
All queries using `session_id`, `flow_id`, or `flow_run_id` benefit from existing indexes.

### N+1 Query Problem
Be aware of the N+1 query problem when loading related data in loops:

**Bad:**
```python
sessions = db.query(TradingSession).all()
for session in sessions:
    # This creates N additional queries!
    decisions = db.query(TradingDecision).filter(
        TradingDecision.session_id == session.id
    ).all()
```

**Good:**
```python
sessions = db.query(TradingSession).all()
session_ids = [s.id for s in sessions]

# Single query for all decisions
decisions = db.query(TradingDecision).filter(
    TradingDecision.session_id.in_(session_ids)
).all()

# Group in Python
from collections import defaultdict
decisions_by_session = defaultdict(list)
for decision in decisions:
    decisions_by_session[decision.session_id].append(decision)
```

---

## Summary

Without foreign key constraints and relationships:
- ✅ More flexible data manipulation
- ✅ Simpler database schema
- ✅ Easier to work with in tests
- ⚠️ Requires manual join queries
- ⚠️ Application-level integrity checks needed
- ⚠️ Manual cascade delete implementation

Use the patterns in this guide to maintain data consistency and query performance.
