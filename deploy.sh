#!/bin/bash
set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to display usage
show_usage() {
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ./deploy.sh [dev|prod]"
    echo -e "\n${YELLOW}Options:${NC}"
    echo -e "  dev   - Deploy development environment"
    echo -e "  prod  - Deploy production environment"
    exit 1
}

# Check if environment argument is provided
if [ $# -ne 1 ]; then
    show_usage
fi

# Set environment variables based on argument
case "$1" in
    "dev")
        ENV="dev"
        TARGET_BRANCH="zeebra-dev"
        COMPOSE_FILE="docker-compose-dev.yml"
        BOT_SERVICE="bb_bot_dev"
        DB_SERVICE="bb_db_dev"
        ADMINER_SERVICE="bb_adminer_dev"
        WEBSITE="bb_website_dev"
        NGINX_SERVICE="bb_nginx_dev"
        ;;
    "prod")
        ENV="prod"
        TARGET_BRANCH="main"
        COMPOSE_FILE="docker-compose.yml"
        BOT_SERVICE="bb_bot_prod"
        DB_SERVICE="bb_db_prod"
        ADMINER_SERVICE="bb_adminer_prod"
        WEBSITE="bb_website_prod"
        NGINX_SERVICE="bb_nginx_prod"
        DASHBOARD="bb_dashboard"
        ;;
    *)
        echo -e "${RED}Error: Invalid environment. Use 'dev' or 'prod'${NC}"
        show_usage
        ;;
esac

# Function to get current branch name
get_current_branch() {
    git rev-parse --abbrev-ref HEAD
}

# Function to check if there are uncommitted changes
has_uncommitted_changes() {
    if git diff-index --quiet HEAD --; then
        return 1  # No changes
    else
        return 0  # Has changes
    fi
}

# Function to check and create network if it doesn't exist
check_network() {
    local network_name=$1
    if ! docker network ls | grep -q "${network_name}"; then
        echo -e "${BLUE}Creating network ${CYAN}${network_name}${NC}"
        docker network create ${network_name}
    else
        echo -e "${GREEN}Network ${CYAN}${network_name}${GREEN} already exists${NC}"
    fi
}

# Function to check if container exists and is running
check_container() {
    local container_name=$1

    # Special handling for bb_bot_dev in dev environment
    if [ "$ENV" = "dev" ] && [ "$container_name" = "bb_bot_dev" ]; then
        echo -e "${YELLOW}Forcing rebuild of ${CYAN}${container_name}${YELLOW}...${NC}"
        docker compose -f ${COMPOSE_FILE} up -d ${container_name} --build --force-recreate
        return 0
    fi

    # Special handling for bb_bot_prod in prod environment
    if [ "$ENV" = "prod" ] && [ "$container_name" = "bb_bot_prod" ]; then
        echo -e "${YELLOW}Forcing rebuild of ${CYAN}${container_name}${YELLOW}...${NC}"
        docker compose -f ${COMPOSE_FILE} up -d ${container_name} --build --force-recreate
        return 0
    fi

    # Normal handling for other containers
    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
            echo -e "${GREEN}Container ${CYAN}${container_name}${GREEN} is already running${NC}"
            return 0
        else
            echo -e "${YELLOW}Container ${CYAN}${container_name}${YELLOW} exists but is not running. Starting it...${NC}"
            docker compose -f ${COMPOSE_FILE} up -d ${container_name} --build
            return 0
        fi
    else
        echo -e "${BLUE}Starting new ${CYAN}${container_name}${BLUE} container${NC}"
        docker compose -f ${COMPOSE_FILE} up -d ${container_name} --build
        return 0
    fi
}

# Main execution starts here
echo -e "${PURPLE}=== Deploying ${CYAN}${ENV}${PURPLE} environment ===${NC}"
echo -e "${PURPLE}=== Checking git branch status... ===${NC}"

CURRENT_BRANCH=$(get_current_branch)

if [ "$CURRENT_BRANCH" != "$TARGET_BRANCH" ]; then
    if has_uncommitted_changes; then
        echo -e "${RED}Error: You have uncommitted changes in your current branch (${CYAN}${CURRENT_BRANCH}${RED}).${NC}"
        echo -e "${RED}Please commit or stash your changes before switching to ${CYAN}${TARGET_BRANCH}${RED}.${NC}"
        exit 1
    else
        echo -e "${YELLOW}Switching from ${CYAN}${CURRENT_BRANCH}${YELLOW} to ${CYAN}${TARGET_BRANCH}${YELLOW}...${NC}"
        git checkout $TARGET_BRANCH
        if [ $? -ne 0 ]; then
            echo -e "${RED}Error: Failed to switch to ${CYAN}${TARGET_BRANCH}${RED} branch.${NC}"
            exit 1
        fi
        echo -e "${GREEN}Successfully switched to ${CYAN}${TARGET_BRANCH}${GREEN} branch.${NC}"
    fi
else
    echo -e "${GREEN}Already on ${CYAN}${TARGET_BRANCH}${GREEN} branch.${NC}"
fi

# Check and create required networks
echo -e "${PURPLE}=== Checking required networks... ===${NC}"
check_network "internal-zeebra"
check_network "nginx-proxy"

# Check each service
echo -e "${PURPLE}=== Checking container status... ===${NC}"
check_container "${DB_SERVICE}"
check_container "${BOT_SERVICE}"
check_container "${ADMINER_SERVICE}"
check_container "${NGINX_SERVICE}"
check_container "${WEBSITE}"
check_container "${DASHBOARD}"

# Start the application
echo -e "${PURPLE}=== Starting application... ===${NC}"