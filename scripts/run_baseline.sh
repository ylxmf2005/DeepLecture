#!/bin/bash
# Performance baseline execution wrapper script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check dependencies
check_dependencies() {
    print_header "Checking Dependencies"

    local all_ok=true

    # Check Python
    if command -v python3 &> /dev/null; then
        print_success "Python 3: $(python3 --version)"
    else
        print_error "Python 3 not found"
        all_ok=false
    fi

    # Check ffmpeg
    if command -v ffmpeg &> /dev/null; then
        print_success "ffmpeg: $(ffmpeg -version | head -n1)"
    else
        print_warning "ffmpeg not found (optional for video test data)"
        print_warning "  Install: brew install ffmpeg (macOS) or apt install ffmpeg (Ubuntu)"
    fi

    # Check psutil
    if python3 -c "import psutil" 2>/dev/null; then
        print_success "psutil: installed"
    else
        print_error "psutil not found"
        echo "  Install: pip install psutil"
        all_ok=false
    fi

    # Check reportlab
    if python3 -c "import reportlab" 2>/dev/null; then
        print_success "reportlab: installed"
    else
        print_warning "reportlab not found (optional for PDF test data)"
        echo "  Install: pip install reportlab"
    fi

    echo ""

    if [ "$all_ok" = false ]; then
        print_error "Missing required dependencies"
        exit 1
    fi
}

# Prepare test data
prepare_test_data() {
    print_header "Preparing Test Data"

    if [ -d "data/test" ]; then
        echo "Test data directory exists: data/test"
        read -p "Regenerate test data? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "Skipping test data generation"
            return
        fi
        rm -rf data/test
    fi

    echo "Generating test data..."
    python3 scripts/prepare_test_data.py --output-dir data/test

    if [ $? -eq 0 ]; then
        print_success "Test data prepared"
        ls -lh data/test/ | head -20
    else
        print_error "Test data preparation failed"
        exit 1
    fi

    echo ""
}

# Run baseline tests
run_baseline() {
    print_header "Running Performance Baseline Tests"

    local iterations=${1:-3}
    local task_types="${2:-}"

    echo "Configuration:"
    echo "  Iterations: $iterations"
    echo "  Task types: ${task_types:-all}"
    echo "  Output: reports/performance/"
    echo ""

    local cmd="python3 scripts/performance_baseline.py --iterations $iterations"

    if [ -n "$task_types" ]; then
        cmd="$cmd --task-types $task_types"
    fi

    echo "Executing: $cmd"
    echo ""

    eval "$cmd"

    if [ $? -eq 0 ]; then
        print_success "Baseline tests completed"
        echo ""
        echo "Reports generated in: reports/performance/"
        ls -lht reports/performance/ | head -10
    else
        print_error "Baseline tests failed"
        exit 1
    fi
}

# Show usage
show_usage() {
    cat << EOF
Performance Baseline Execution Script

Usage:
  $0 [options]

Options:
  --check           Check dependencies only
  --prepare         Prepare test data only
  --dry-run         Show test scenarios without executing
  --iterations N    Number of iterations per scenario (default: 3)
  --task-types ...  Specific task types to test (space-separated)
  --help            Show this help message

Examples:
  # Full baseline with default settings
  $0

  # Check dependencies
  $0 --check

  # Prepare test data only
  $0 --prepare

  # Dry run (preview scenarios)
  $0 --dry-run

  # Run with 5 iterations
  $0 --iterations 5

  # Test specific task types
  $0 --task-types subtitle_generation subtitle_translation

  # Full pipeline with 5 iterations
  $0 --iterations 5

EOF
}

# Main execution
main() {
    print_header "Performance Baseline - Phase 0"

    # Parse arguments
    local check_only=false
    local prepare_only=false
    local dry_run=false
    local iterations=3
    local task_types=""

    while [[ $# -gt 0 ]]; do
        case $1 in
            --check)
                check_only=true
                shift
                ;;
            --prepare)
                prepare_only=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --iterations)
                iterations="$2"
                shift 2
                ;;
            --task-types)
                shift
                task_types="$*"
                break
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Execute based on options
    if [ "$check_only" = true ]; then
        check_dependencies
        exit 0
    fi

    check_dependencies

    if [ "$prepare_only" = true ]; then
        prepare_test_data
        exit 0
    fi

    if [ "$dry_run" = true ]; then
        print_header "Dry Run - Preview Test Scenarios"
        python3 scripts/performance_baseline.py --dry-run
        exit 0
    fi

    # Full execution
    prepare_test_data
    run_baseline "$iterations" "$task_types"

    print_header "Baseline Execution Complete"
    print_success "Phase 0 baseline established"
    echo ""
    echo "Next steps:"
    echo "  1. Review reports/performance/baseline_report_*.md"
    echo "  2. Validate metrics with team"
    echo "  3. Set up monitoring dashboard"
    echo "  4. Begin Phase 1 refactoring"
    echo ""
}

main "$@"
