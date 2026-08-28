# Herdr VPS shell paths. Safe to source repeatedly from Bash or Zsh.
case ":${PATH:-}:" in
  *":$HOME/.hermes/bin:"*) ;;
  *) PATH="$HOME/.hermes/bin${PATH:+:$PATH}" ;;
esac
case ":${PATH:-}:" in
  *":$HOME/.grok/bin:"*) ;;
  *) PATH="$HOME/.grok/bin${PATH:+:$PATH}" ;;
esac
case ":${PATH:-}:" in
  *":$HOME/.local/bin:"*) ;;
  *) PATH="$HOME/.local/bin${PATH:+:$PATH}" ;;
esac
export PATH

# Route any tool that honors $BROWSER (OAuth flows, harness "open this" links)
# through the reverse-SSH hop to Chrome on the Mac. Harmless without a tunnel:
# herdr-open-url just fails fast.
case ":${BROWSER:-}:" in
  *":$HOME/.local/bin/herdr-open-url:"*) ;;
  *) export BROWSER="$HOME/.local/bin/herdr-open-url" ;;
esac
