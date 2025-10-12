# GitHub Actions CI/CD Pipeline

This directory contains the GitHub Actions workflows for the PIX Historial project.

## 🚀 Main CI/CD Pipeline

### File: `ci.yml`

The main pipeline that provides comprehensive testing, security scanning, and safe deployment.

#### Workflow Triggers
- **Push to `main`**: Runs full pipeline and deploys to production
- **Push to `dev`**: Runs tests and deploys to staging
- **Pull Requests**: Runs all tests and security checks

#### Jobs Overview

##### 1. **test** - Comprehensive Testing
- **Multi-Python Support**: Tests on Python 3.11, 3.12, and 3.13
- **Code Quality**: 
  - `ruff` for linting
  - `black` for code formatting
  - `isort` for import sorting
  - `mypy` for type checking
- **Test Coverage**: 
  - Runs all 102 tests
  - Enforces 80% minimum coverage
  - Uploads coverage reports to Codecov

##### 2. **security** - Security Scanning
- **Bandit**: Python security linter for common vulnerabilities
- **Safety**: Checks for known security vulnerabilities in dependencies
- **Trivy**: Container and filesystem vulnerability scanner
- **SARIF Upload**: Integrates with GitHub Security tab

##### 3. **build** - Application Validation
- Validates application can import and start
- Generates build information
- Ensures all dependencies are compatible

##### 4. **deploy-staging** - Staging Deployment
- Triggers on pushes to `dev` branch
- Deploys to staging environment
- Runs after all tests pass

##### 5. **deploy-production** - Production Deployment
- Triggers on pushes to `main` branch
- **Safe Deployment Features**:
  - Creates automatic backup before deployment
  - Runs health checks with 30-second timeout
  - Automatic rollback on health check failure
  - Deployment verification
  - Comprehensive logging

## 🔐 Required Secrets

### Production Deployment
- `DEPLOY_KEY`: SSH private key for server access
- `SERVER_HOST`: Production server hostname/IP
- `SERVER_USER`: SSH username for server access
- `APP_LOCATION`: Path to application on server

### Optional (for enhanced features)
- `CODECOV_TOKEN`: For coverage reporting integration

## 🏗️ Environment Setup

### GitHub Environments
- **production**: Protected environment for production deployments
- **staging**: Environment for staging deployments

### Protection Rules (Recommended)
```yaml
# Production environment should require:
- Approval from at least 1 reviewer
- Wait timer of 5 minutes
- Restrict deployments to main branch only

# Staging environment (dev branch):
- No approval required (for rapid iteration)
- Automatic deployment on push to dev
```

## 📊 Pipeline Status Badges

Add these badges to your README.md:

```markdown
![CI/CD](https://github.com/Giygas/pix-historial/actions/workflows/ci.yml/badge.svg)
![Coverage](https://codecov.io/gh/Giygas/pix-historial/branch/main/graph/badge.svg)
```

## 🛠️ Local Development

### Running Tests Locally
```bash
# Run all tests with coverage
python -m pytest tests/ --cov=app --cov-report=term-missing

# Run linting
python -m ruff check app/ tests/
python -m black --check app/ tests/
python -m isort --check-only app/ tests/

# Run type checking
python -m mypy app/

# Run security checks
bandit -r app/
safety check
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## 🚨 Deployment Process

### Production Deployment Flow
1. **Code pushed to `main` branch**
2. **Pipeline triggers automatically**
3. **Test suite runs** (102 tests across 3 Python versions)
4. **Security scanning** (Bandit, Safety, Trivy)
5. **Build validation** (application import test)
6. **Production deployment**:
   - Creates backup of current version
   - Pulls latest code
   - Installs dependencies
   - Restarts service
   - Runs health checks (30-second timeout)
   - **If health check fails**: Automatic rollback
   - **If health check passes**: Deployment verified

### Staging Deployment Flow
1. **Code pushed to `dev` branch**
2. **Runs tests and security checks**
3. **Deploys to staging environment**
4. **No health checks required** (staging)

## 🔍 Monitoring and Troubleshooting

### Viewing Pipeline Results
1. Go to **Actions** tab in GitHub repository
2. Click on the workflow run
3. View detailed logs for each job

### Common Issues

#### Test Failures
- Check test logs for specific failure details
- Run tests locally to reproduce issues
- Verify all dependencies are installed

#### Security Scan Failures
- Review Bandit/Safety reports
- Update vulnerable dependencies
- Fix security issues in code

#### Deployment Failures
- Check deployment logs
- Verify server connectivity
- Review health check endpoint
- Check service logs on server

### Rollback Process
If deployment fails, the pipeline automatically:
1. Stops the service
2. Restores from backup
3. Restarts the service
4. Reports rollback status

## 📈 Performance Metrics

### Pipeline Performance
- **Test Duration**: ~2-3 minutes
- **Security Scan**: ~1-2 minutes
- **Deployment**: ~1-2 minutes
- **Total Pipeline**: ~5-8 minutes

### Coverage Requirements
- **Minimum Coverage**: 80%
- **Current Coverage**: 85%
- **Tests Passing**: 102/102

## 🔄 Migration from Old Workflow

The old `deploy.yml` workflow has been deprecated and replaced with the comprehensive `ci.yml` pipeline.

### Key Improvements
- ✅ **Added comprehensive testing** (was missing)
- ✅ **Fixed SSH security** (removed `StrictHostKeyChecking=no`)
- ✅ **Added health checks** (was missing)
- ✅ **Added automatic rollback** (was missing)
- ✅ **Added security scanning** (was missing)
- ✅ **Updated GitHub Actions** (was using outdated versions)

### Migration Steps
1. ✅ New pipeline created and active
2. ✅ Old pipeline disabled and marked as deprecated
3. ✅ All secrets and configurations remain the same
4. ✅ Enhanced deployment safety features added

## 🎯 Best Practices Implemented

### Security
- ✅ SSH host key verification
- ✅ Secret management
- ✅ Vulnerability scanning
- ✅ Environment protection

### Reliability
- ✅ Comprehensive testing
- ✅ Health checks
- ✅ Automatic rollback
- ✅ Multi-Python testing

### Quality
- ✅ Code formatting checks
- ✅ Type checking
- ✅ Coverage requirements
- ✅ Linting

### Monitoring
- ✅ Detailed logging
- ✅ Deployment verification
- ✅ Status notifications
- ✅ Artifact preservation

---

This CI/CD pipeline ensures that only high-quality, tested, and secure code is deployed to production while maintaining reliability and providing comprehensive monitoring.