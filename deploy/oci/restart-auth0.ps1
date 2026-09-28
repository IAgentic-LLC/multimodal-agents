$ErrorActionPreference = "Stop"

function Get-ContainerVariable([string]$Container, [string]$Name) {
    $inspect = docker inspect $Container | ConvertFrom-Json
    $entry = $inspect[0].Config.Env |
        Where-Object { $_.StartsWith("$Name=") } |
        Select-Object -First 1
    if (-not $entry) {
        throw "Required container variable is missing: $Name"
    }
    return $entry.Substring($Name.Length + 1)
}

$env:POSTGRES_ADMIN_PASSWORD = Get-ContainerVariable `
    "multimodal-postgres" "POSTGRES_PASSWORD"
$env:STUDIO_APP_PASSWORD = Get-ContainerVariable `
    "multimodal-postgres" "STUDIO_APP_PASSWORD"
$env:AUTH_MODE = "auth0"
$env:ALLOW_INSECURE_LOCAL_TENANT = "false"
$env:AUTH0_DOMAIN = "dev-a73uyb0st1rx7y8q.eu.auth0.com"
$env:AUTH0_AUDIENCE = "https://multimodal-agent-studio.dev/api"

docker compose -p book6test -f "$PSScriptRoot\docker-compose.yml" `
    up -d --build studio-api multimodal-studio
