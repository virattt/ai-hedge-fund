# Architecture Breakdown

## Current System Architecture

### Main Entry Points

- `src/main.py` - Main hedge fund analysis orchestrator with dotenv support
- `src/backtester.py` - Portfolio backtesting system
- `screen_stocks.py` - Stock screening utility

### Core Components

#### Data Layer (Current)

- **API Client**: `src/tools/api.py` - Direct integration with financialdatasets.ai
- **Cache Layer**: `src/data/cache.py` - In-memory caching for API responses
- **Data Models**: `src/data/models.py` - Pydantic models for all financial data types

#### Agent System

- **Multi-Agent Framework**: 20+ financial analysts (Warren Buffett, Charlie Munger, etc.)
- **State Management**: `src/graph/state.py` - Centralized state for agent coordination
- **Analysis Pipeline**: Parallel execution with progress tracking

#### Financial Analysis

- **Valuation**: `src/agents/valuation.py` - Multi-methodology valuation analysis
- **Investment Agents**: Individual analyst agents with distinct investment philosophies
- **Screening**: `src/screening/` - Stock screening algorithms

### Current Dependencies

- **Primary Data Source**: financialdatasets.ai API (tightly coupled)
- **Rate Limiting**: Configurable (default 90 calls/minute)
- **Caching**: In-memory only (no persistence)

### Current Architecture Issues

1. **Single Point of Failure**: 100% dependent on financialdatasets.ai
2. **High API Costs**: Hundreds of calls per stock analysis
3. **No Data Persistence**: Cache lost on restart
4. **Rate Limiting Constraints**: Limited throughput for large analyses
5. **No Data Sovereignty**: No local data ownership

## NEXT OBJECTIVE: Data Abstraction Layer Implementation

### Proposed Architecture (Priority Implementation)

#### Repository Pattern Implementation

- **Interface Layer**: `IFinancialDataRepository` abstraction
- **Database Repository**: Local PostgreSQL implementation
- **API Repository**: Existing financialdatasets.ai wrapper
- **Hybrid Repository**: Database-first with API fallback
- **Factory Pattern**: Strategy-based repository selection

#### Data Storage Strategy

- **Local Database**: PostgreSQL for persistent data storage
- **Bulk Collection Service**: Scheduled API data harvesting
- **Data Freshness**: Intelligent cache invalidation
- **Fallback Mechanism**: Seamless API fallback for missing data

#### Benefits

1. **Cost Reduction**: 90%+ reduction in API calls after initial data collection
2. **Performance**: Local queries 10-100x faster than API calls
3. **Reliability**: Eliminates dependency on third-party availability
4. **Data Sovereignty**: Complete ownership of financial data
5. **Scalability**: Support for larger stock universes

### Implementation Phases

#### Phase 1: Repository Foundation

- Create `IFinancialDataRepository` interface
- Implement database schema design
- Set up PostgreSQL connection pooling

#### Phase 2: Database Implementation

- Create `DatabaseFinancialRepository`
- Implement data persistence layer
- Add database migrations

#### Phase 3: Hybrid Strategy

- Implement `HybridFinancialRepository`
- Create fallback logic (DB → API)
- Add automatic data backfill

#### Phase 4: Data Collection Service

- Build bulk data collection pipeline
- Implement rate-limited API harvesting
- Add scheduling and monitoring

#### Phase 5: Migration & Testing

- Update existing agents to use repository pattern
- Comprehensive testing of all data paths
- Performance benchmarking

#### Phase 6: Monitoring & Optimization

- Data freshness monitoring
- Query performance optimization
- Cost analysis and reporting

### SOLID Principles Adherence

- **Single Responsibility**: Each repository handles one data source
- **Open/Closed**: Easy to add new data sources without modifying existing code
- **Liskov Substitution**: All repositories interchangeable via interface
- **Interface Segregation**: Focused repository interface
- **Dependency Inversion**: Agents depend on abstractions, not concrete implementations

### Technology Stack Decision Required

- **Database**: PostgreSQL vs SQL Server evaluation needed
- **ORM**: SQLAlchemy vs raw SQL consideration
- **Connection**: asyncpg vs psycopg3 for PostgreSQL
- **Migration**: Alembic for schema management
