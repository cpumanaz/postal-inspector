require ["fileinto", "mailbox", "envelope", "variables"];

# Default sieve rules for mail sorting
# Customize these patterns to match your email setup

# Service accounts pattern: svc-<folder>@domain goes to <folder>
# Example: svc-github@example.com -> github folder
# Example: svc-aws@example.com -> aws folder
if envelope :matches "to" "svc-*@*" {
    set :lower "folder" "${1}";
    fileinto :create "${folder}";
    stop;
}

# Fallback - keep everything else in INBOX
keep;
