#!/bin/bash
# Beta deployment script for DebtWise API

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$DEPLOYMENT_DIR/docker-compose.beta.yml"
ENV_FILE="$DEPLOYMENT_DIR/.env"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check environment file
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found at $ENV_FILE"
        log_info "Please copy .env.example to .env and configure it"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Pull latest images
pull_images() {
    log_info "Pulling latest images..."
    docker-compose -f "$COMPOSE_FILE" pull
    log_success "Images pulled successfully"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    docker-compose -f "$COMPOSE_FILE" run --rm api alembic upgrade head
    log_success "Migrations completed"
}

# Health check
health_check() {
    log_info "Performing health check..."
    
    # Wait for services to be ready
    sleep 10
    
    # Check API health
    if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        log_success "API health check passed"
    else
        log_error "API health check failed"
        return 1
    fi
    
    return 0
}

# Main deployment process
deploy() {
    log_info "Starting DebtWise Beta deployment..."
    
    # Check prerequisites
    check_prerequisites
    
    # Create required directories
    mkdir -p "$DEPLOYMENT_DIR/logs" "$DEPLOYMENT_DIR/backup"
    
    # Pull latest images
    pull_images
    
    # Stop existing services
    log_info "Stopping existing services..."
    docker-compose -f "$COMPOSE_FILE" down
    
    # Start infrastructure services first
    log_info "Starting infrastructure services..."
    docker-compose -f "$COMPOSE_FILE" up -d db redis
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 10
    
    # Run migrations
    run_migrations
    
    # Start all services
    log_info "Starting all services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    # Perform health check
    if health_check; then
        log_success "Deployment completed successfully!"
        
        # Show service status
        echo ""
        log_info "Service Status:"
        docker-compose -f "$COMPOSE_FILE" ps
        
        echo ""
        log_info "Access points:"
        echo "  - API: https://beta-api.debtwise.com"
        echo "  - Monitoring: https://beta-monitoring.debtwise.com"
        echo "  - Health Check: https://beta-api.debtwise.com/api/v1/health"
        
    else
        log_error "Deployment failed!"
        log_info "Check logs with: docker-compose -f $COMPOSE_FILE logs"
        exit 1
    fi
}

# Rollback function
rollback() {
    log_warning "Rolling back deployment..."
    
    # Stop current services
    docker-compose -f "$COMPOSE_FILE" down
    
    # Restore from backup if available
    if [ -f "$DEPLOYMENT_DIR/backup/rollback-tag.txt" ]; then
        ROLLBACK_TAG=$(cat "$DEPLOYMENT_DIR/backup/rollback-tag.txt")
        log_info "Rolling back to image tag: $ROLLBACK_TAG"
        
        # Update image tag in environment
        sed -i.bak "s/GITHUB_SHA=.*/GITHUB_SHA=$ROLLBACK_TAG/" "$ENV_FILE"
        
        # Deploy previous version
        docker-compose -f "$COMPOSE_FILE" up -d
        
        log_success "Rollback completed"
    else
        log_error "No rollback tag found"
        exit 1
    fi
}

# Main script logic
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    rollback)
        rollback
        ;;
    status)
        docker-compose -f "$COMPOSE_FILE" ps
        ;;
    logs)
        docker-compose -f "$COMPOSE_FILE" logs -f ${2:-}
        ;;
    restart)
        docker-compose -f "$COMPOSE_FILE" restart ${2:-}
        ;;
    *)
        echo "Usage: $0 {deploy|rollback|status|logs|restart}"
        exit 1
        ;;
esac