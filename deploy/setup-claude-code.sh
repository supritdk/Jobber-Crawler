#!/usr/bin/env bash
#
# setup-claude-code.sh — Install Claude Code on EC2 for live development
#
# Usage:
#   chmod +x deploy/setup-claude-code.sh && ./deploy/setup-claude-code.sh
#
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

# ─── Step 1: Install Node.js ────────────────────────────────────────────────
if command -v node &> /dev/null; then
    info "Node.js already installed: $(node --version)"
else
    info "Installing Node.js 22 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt install -y -qq nodejs
    info "Node.js installed: $(node --version)"
fi

# ─── Step 2: Install Claude Code ────────────────────────────────────────────
if command -v claude &> /dev/null; then
    info "Claude Code already installed: $(claude --version 2>/dev/null || echo 'installed')"
else
    info "Installing Claude Code..."
    sudo npm install -g @anthropic-ai/claude-code
    info "Claude Code installed."
fi

# ─── Step 3: Configure API key ──────────────────────────────────────────────
if grep -q "ANTHROPIC_API_KEY" ~/.bashrc 2>/dev/null; then
    info "ANTHROPIC_API_KEY already in .bashrc"
else
    echo ""
    read -rp "Enter your Anthropic API key (sk-ant-...): " api_key
    if [ -n "$api_key" ]; then
        echo "" >> ~/.bashrc
        echo "# Claude Code" >> ~/.bashrc
        echo "export ANTHROPIC_API_KEY=\"${api_key}\"" >> ~/.bashrc
        export ANTHROPIC_API_KEY="${api_key}"
        info "API key saved to ~/.bashrc"
    else
        warn "Skipped — set ANTHROPIC_API_KEY manually before using Claude Code."
    fi
fi

# ─── Step 4: tmux for persistent sessions ───────────────────────────────────
if ! command -v tmux &> /dev/null; then
    info "Installing tmux (keeps Claude Code alive if SSH disconnects)..."
    sudo apt install -y -qq tmux
fi

# Create a convenience alias
if ! grep -q "alias jc=" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << 'ALIASEOF'

# Jobber Crawler shortcuts
alias jc='cd ~/jobber-crawler && claude'
alias jc-logs='sudo journalctl -u jobber-crawler -f'
alias jc-restart='sudo systemctl restart jobber-crawler'
alias jc-status='sudo systemctl status jobber-crawler'
ALIASEOF
    info "Added shell aliases: jc, jc-logs, jc-restart, jc-status"
fi

# ─── Done ────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Claude Code is ready!"
echo ""
echo "  Start developing:"
echo "    cd ~/jobber-crawler && claude"
echo ""
echo "  Or use the shortcut:"
echo "    jc"
echo ""
echo "  Tip: Use tmux for persistent sessions:"
echo "    tmux new -s dev"
echo "    jc"
echo "    # Detach: Ctrl+B then D"
echo "    # Reattach: tmux attach -t dev"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
