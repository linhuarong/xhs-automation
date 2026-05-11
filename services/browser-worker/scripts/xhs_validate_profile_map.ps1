param(
    [string]$ProfileMapPath = ".config/kuaijingvs_profiles.json"
)

$ErrorActionPreference = "Stop"
$AllowedProviderTypes = @(
    "kuaijingvs_yingdao_rpa",
    "yingdao_rpa",
    "manual",
    "selenium_chrome_debug"
)

if (-not (Test-Path $ProfileMapPath)) {
    Write-Error "profile map not found: $ProfileMapPath"
    exit 1
}

try {
    $profileMap = Get-Content -Raw -Encoding UTF8 $ProfileMapPath | ConvertFrom-Json
}
catch {
    Write-Error "profile map JSON invalid: $ProfileMapPath"
    exit 1
}

if ($null -eq $profileMap -or $profileMap.PSObject.Properties.Count -eq 0) {
    Write-Error "profile map must be a non-empty JSON object"
    exit 1
}

foreach ($property in $profileMap.PSObject.Properties) {
    $accountId = $property.Name
    $profile = $property.Value
    foreach ($field in @("shop_id", "shop_name", "provider_type")) {
        if (-not $profile.PSObject.Properties[$field] -or [string]::IsNullOrWhiteSpace([string]$profile.$field)) {
            Write-Error "profile map entry $accountId missing field: $field"
            exit 1
        }
    }
    if ($AllowedProviderTypes -notcontains [string]$profile.provider_type) {
        Write-Error "profile map entry $accountId has unsupported provider_type: $($profile.provider_type)"
        exit 1
    }
}

Write-Output "profile map valid: $ProfileMapPath"
Write-Output "profile count: $($profileMap.PSObject.Properties.Count)"
