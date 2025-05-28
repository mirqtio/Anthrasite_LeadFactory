# Pipeline Stage Requirements Analysis

## Overview

This document analyzes the actual pipeline stages in the LeadFactory system and defines their specific validation requirements. The current PipelineValidator validates fictional microservices that don't exist, while the real pipeline consists of lead generation stages.

## Current vs. Actual Pipeline Stages

### Current PipelineValidator (Incorrect)
- `data_ingestion` - Does not exist
- `data_processing` - Does not exist
- `model_training` - Does not exist
- `api_gateway` - Does not exist
- `notification_service` - Does not exist

### Actual Pipeline Stages (Correct)
1. **Scrape** (`01_scrape.py` → `leadfactory.pipeline.scrape`)
2. **Screenshot** (`02_screenshot.py` → `leadfactory.pipeline.screenshot`)
3. **Mockup** (`03_mockup.py` → `leadfactory.pipeline.mockup`)
4. **Personalize** (`04_personalize.py` → personalization logic)
5. **Render** (`05_render.py` → rendering logic)
6. **Email Queue** (`06_email_queue.py` → `leadfactory.pipeline.email_queue`)

## Stage-by-Stage Validation Requirements

### 1. Scrape Stage
**Module**: `leadfactory.pipeline.scrape`
**Purpose**: Scrapes business data from various sources

**Validation Requirements**:
- **Dependencies**:
  - Database connection (PostgreSQL)
  - External APIs (business data sources)
  - Configuration files (`config.yaml`)
- **Environment Variables**:
  - Database connection strings
  - API keys for data sources
  - Rate limiting configuration
- **Resources**:
  - Network connectivity
  - Sufficient disk space for data storage
  - Memory for processing large datasets
- **Permissions**:
  - Database read/write access
  - File system write access
- **Edge Cases**:
  - API rate limiting
  - Network timeouts
  - Invalid ZIP codes
  - Database connection failures

### 2. Screenshot Stage
**Module**: `leadfactory.pipeline.screenshot`
**Purpose**: Captures screenshots of business websites

**Validation Requirements**:
- **Dependencies**:
  - Browser automation tools (Selenium/Playwright)
  - Database connection for business URLs
  - Image storage system
- **Environment Variables**:
  - Browser configuration
  - Screenshot storage paths
  - Timeout settings
- **Resources**:
  - Browser binaries installed
  - Sufficient disk space for images
  - Graphics/display capabilities
- **Permissions**:
  - File system write access
  - Network access to business websites
- **Edge Cases**:
  - Websites that block automation
  - SSL certificate issues
  - Timeout on slow websites
  - Invalid URLs

### 3. Mockup Stage
**Module**: `leadfactory.pipeline.mockup`
**Purpose**: Generates mockup designs for businesses

**Validation Requirements**:
- **Dependencies**:
  - Design templates
  - Image processing libraries
  - Database connection for business data
- **Environment Variables**:
  - Template paths
  - Output directories
  - Design configuration
- **Resources**:
  - Template files accessible
  - Sufficient disk space for mockups
  - Image processing capabilities
- **Permissions**:
  - File system read/write access
  - Template directory access
- **Edge Cases**:
  - Missing business logos
  - Template rendering failures
  - Insufficient business data

### 4. Personalize Stage
**Module**: Personalization logic
**Purpose**: Personalizes content for specific businesses

**Validation Requirements**:
- **Dependencies**:
  - Business data from previous stages
  - Personalization templates
  - Configuration for personalization rules
- **Environment Variables**:
  - Personalization settings
  - Template configurations
- **Resources**:
  - Access to business data
  - Template processing capabilities
- **Permissions**:
  - Database read access
  - Template file access
- **Edge Cases**:
  - Incomplete business data
  - Template processing errors

### 5. Render Stage
**Module**: Rendering logic
**Purpose**: Renders final output for email campaigns

**Validation Requirements**:
- **Dependencies**:
  - Rendering engine
  - Templates and assets
  - Business data and mockups
- **Environment Variables**:
  - Rendering configuration
  - Output formats
- **Resources**:
  - Rendering engine availability
  - Sufficient processing power
- **Permissions**:
  - File system access
  - Template directory access
- **Edge Cases**:
  - Rendering engine failures
  - Asset loading issues

### 6. Email Queue Stage
**Module**: `leadfactory.pipeline.email_queue`
**Purpose**: Manages email campaign generation and delivery

**Validation Requirements**:
- **Dependencies**:
  - Email service provider (ESP) APIs
  - Database connection
  - Email templates
  - Rendered content from previous stages
- **Environment Variables**:
  - ESP API keys and configuration
  - SMTP settings
  - Email template paths
  - Queue configuration
- **Resources**:
  - Network connectivity to ESP
  - Database storage for queue
  - Email template files
- **Permissions**:
  - Database read/write access
  - Network access to ESP APIs
  - File system access for templates
- **Edge Cases**:
  - ESP API rate limits
  - Invalid email addresses
  - Template rendering failures
  - Queue processing errors

## Additional Pipeline Components

### Supporting Modules
- **Dedupe** (`leadfactory.pipeline.dedupe_unified`): Deduplication logic
- **Enrich** (`leadfactory.pipeline.enrich`): Data enrichment
- **Score** (`leadfactory.pipeline.score`): Business scoring
- **Conflict Resolution** (`leadfactory.pipeline.conflict_resolution`): Handle data conflicts
- **Data Preservation** (`leadfactory.pipeline.data_preservation`): Preserve data integrity
- **Manual Review** (`leadfactory.pipeline.manual_review`): Manual review processes

### Cross-Stage Dependencies
1. **Database Connection**: All stages require PostgreSQL connectivity
2. **Configuration**: All stages need access to `config.yaml`
3. **Logging**: All stages use unified logging system
4. **Metrics**: All stages report to metrics system
5. **Error Handling**: All stages need proper error propagation

## Validation Strategy

### Stage-Specific Validation
Each stage should validate:
1. **Module Import**: Can the stage module be imported?
2. **Dependencies**: Are required dependencies available?
3. **Configuration**: Is stage configuration valid?
4. **Resources**: Are required resources accessible?
5. **Permissions**: Does the stage have necessary permissions?

### Integration Validation
Between stages:
1. **Data Flow**: Can data flow from one stage to the next?
2. **Format Compatibility**: Are data formats compatible?
3. **Dependency Chain**: Are stage dependencies satisfied?

### Environment Modes
- **E2E Mode**: Minimal validation for testing
- **Production Mode**: Full validation requirements
- **Mock Mode**: Simulated validation for development

## Recommendations

1. **Refactor PipelineValidator** to validate actual pipeline stages
2. **Implement stage-specific validation methods** for each pipeline component
3. **Add dependency checking** between stages
4. **Create comprehensive error reporting** for validation failures
5. **Add integration tests** for stage-to-stage data flow
6. **Implement health checks** for external dependencies (APIs, databases)

## Next Steps

1. Implement validation rules for each stage
2. Create dependency checking system
3. Enhance error reporting
4. Develop comprehensive test coverage
5. Update documentation and configuration examples
