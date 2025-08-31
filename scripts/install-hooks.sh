#!/bin/bash

# Install git hooks for shechill-analysis project
# Run this script from the repository root

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[HOOK-INSTALL]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" ]]; then
    print_error "Not in project root directory. Please run from repository root."
    exit 1
fi

# Check if .git directory exists
if [[ ! -d ".git" ]]; then
    print_error "Not in a git repository. Please run from repository root."
    exit 1
fi

print_status "Installing git hooks for shechill-analysis..."

# Create hooks directory if it doesn't exist
mkdir -p .git/hooks

# Pre-push hook content
cat > .git/hooks/pre-push << 'EOF'
#!/bin/bash

# Pre-push hook for shechill-analysis
# Runs code quality checks before allowing push

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[PRE-PUSH]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" ]]; then
    print_error "Not in project root directory. Please run from repository root."
    exit 1
fi

# Check if dev dependencies are installed
if ! python -c "import black, flake8, isort, mypy" 2>/dev/null; then
    print_error "Development dependencies not installed. Run: pip install -e \".[dev]\""
    exit 1
fi

print_status "Running pre-push checks..."

# Track if any checks fail
CHECKS_FAILED=0

# 1. Check code formatting with black
print_status "Checking code formatting with black..."
if black --check --quiet src/ web/ 2>/dev/null; then
    print_success "Code formatting is correct"
else
    print_error "Code formatting issues found. Run: black src/ web/"
    CHECKS_FAILED=1
fi

# 2. Check import sorting with isort
print_status "Checking import sorting with isort..."
if isort --check-only --quiet src/ web/ 2>/dev/null; then
    print_success "Import sorting is correct"
else
    print_error "Import sorting issues found. Run: isort src/ web/"
    CHECKS_FAILED=1
fi

# 3. Run flake8 linting (critical errors only for speed)
print_status "Running flake8 linting (critical errors)..."
if flake8 src/ web/ --select=E9,F63,F7,F82 --quiet 2>/dev/null; then
    print_success "No critical linting errors found"
else
    print_error "Critical linting errors found. Run: flake8 src/ web/"
    CHECKS_FAILED=1
fi

# 4. Run mypy type checking
print_status "Running mypy type checking..."
if mypy src/ web/ --ignore-missing-imports --no-strict-optional >/dev/null 2>&1; then
    print_success "Type checking passed"
else
    print_error "Type checking errors found. Run: mypy src/ web/ --ignore-missing-imports --no-strict-optional"
    CHECKS_FAILED=1
fi

# 5. Basic smoke test (import check)
print_status "Running smoke test (import check)..."
if python -c "
import sys
sys.path.append('src')
sys.path.append('web')
try:
    from src.config_manager import ConfigManager
    from web.app import app
    print('✅ Basic imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
" 2>/dev/null; then
    print_success "Smoke test passed"
else
    print_error "Smoke test failed. Check import errors."
    CHECKS_FAILED=1
fi

# Summary
echo ""
if [[ $CHECKS_FAILED -eq 0 ]]; then
    print_success "All pre-push checks passed! 🚀"
    echo ""
else
    print_error "Some checks failed. Please fix the issues above before pushing."
    echo ""
    print_warning "To skip these checks (not recommended), use: git push --no-verify"
    exit 1
fi
EOF

# Make the hook executable
chmod +x .git/hooks/pre-push

print_success "Pre-push hook installed successfully!"
echo ""
print_status "The hook will now run automatically before every 'git push'"
print_status "To test the hook, try: git push --dry-run"
print_status "To skip the hook (not recommended), use: git push --no-verify"
echo ""
print_warning "Make sure you have development dependencies installed:"
echo "  pip install -e \".[dev]\""