FROM python:3.12-slim

# Prerequisites for setup.py plus Homebrew-on-Linux (build-essential, file,
# procps, curl, git) so the Install Homebrew path is testable too.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        file \
        git \
        procps \
        sudo \
    && rm -rf /var/lib/apt/lists/*

ARG USERNAME=dev

# Non-root user with passwordless sudo (the Homebrew installer needs it).
RUN useradd --create-home --shell /bin/bash "$USERNAME" \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/"$USERNAME" \
    && chmod 0440 /etc/sudoers.d/"$USERNAME" \
    && mkdir -p /home/"$USERNAME"/dotfiles/.setup-venv \
    && chown -R "$USERNAME":"$USERNAME" /home/"$USERNAME"/dotfiles

USER $USERNAME
WORKDIR /home/$USERNAME/dotfiles

CMD ["sleep", "infinity"]
