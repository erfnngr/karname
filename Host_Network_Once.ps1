param([string]$ResultPath = (Join-Path $PSScriptRoot 'Network-Ready.json'))
$ErrorActionPreference = 'Stop'
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    $quoted = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -ResultPath "' + $ResultPath + '"'
    $elevated = Start-Process -FilePath 'powershell.exe' -ArgumentList $quoted -Verb RunAs -WindowStyle Hidden -PassThru
    $elevated.WaitForExit()
    exit $elevated.ExitCode
}
$program = 'C:\Users\ali\AppData\Local\Programs\Karname\Karname.exe'
$utf8 = New-Object System.Text.UTF8Encoding($false)
try {
    if (-not (Test-Path -LiteralPath $program)) { throw 'The company host executable is not installed.' }
    $oldBlocks = @(Get-NetFirewallRule -Direction Inbound -Enabled True -Action Block | Where-Object {
        ($_ | Get-NetFirewallApplicationFilter).Program -eq $program -and $_.Name -notin @('Karname-Auto-Company-HTTPS-OtherNetworks','Karname-Auto-Company-Discovery-OtherNetworks')
    })
    foreach ($block in $oldBlocks) {
        $portFilter = $block | Get-NetFirewallPortFilter
        $expected = if ($portFilter.Protocol -eq 'TCP') { '1-8842,8844-65535' } else { '1-8843,8845-65535' }
        $actualPorts = ($portFilter.LocalPort | Sort-Object) -join ','
        if ($block.Name -notlike '*Query User*' -or $block.PolicyStoreSourceType.ToString() -ne 'Local' -or ($actualPorts -ne 'Any' -and $actualPorts -ne $expected) -or $portFilter.Protocol -notin @('TCP','UDP')) { throw 'An administrator-defined block exists and was preserved.' }
    }
    if ($oldBlocks.Count -and -not (Test-Path -LiteralPath ($ResultPath+'.previous-rules.json'))) {
        $snapshot = @($oldBlocks | ForEach-Object { $p=$_|Get-NetFirewallPortFilter; @{name=$_.Name;protocol=$p.Protocol;local_port=$p.LocalPort;action='Block';enabled=$true} })
        [IO.File]::WriteAllText(($ResultPath+'.previous-rules.json'),($snapshot|ConvertTo-Json -Depth 4),$utf8)
    }
    # Keep explicit blocking outside the requested LAN, including the model relay.
    # The loopback network is retained for the host's own internal connection.
    $outside = @('0.0.0.0-126.255.255.255','128.0.0.0-192.168.99.255','192.168.101.0-255.255.255.255','::/0')
    foreach ($rule in @(@{Name='Karname-Auto-Company-HTTPS';Protocol='TCP';Port=8843},@{Name='Karname-Auto-Company-Discovery';Protocol='UDP';Port=8844})) {
        $outsideName = $rule.Name+'-OtherNetworks'
        if (-not (Get-NetFirewallRule -Name $outsideName -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -Name $outsideName -DisplayName $outsideName -Program $program -Direction Inbound -Action Block -Enabled True -Profile Any -Protocol $rule.Protocol -LocalPort $rule.Port -RemoteAddress $outside -ErrorAction Stop | Out-Null
        }
        $existing = Get-NetFirewallRule -Name $rule.Name -ErrorAction SilentlyContinue
        if ($existing) {
            $application = $existing | Get-NetFirewallApplicationFilter
            if ($application.Program -ne $program -or $existing.Action.ToString() -ne 'Allow') { throw 'An unrelated firewall rule exists and was preserved.' }
        } else {
            New-NetFirewallRule -Name $rule.Name -DisplayName $rule.Name -Program $program -Direction Inbound -Action Allow -Enabled True -Profile Private,Public -Protocol $rule.Protocol -LocalPort $rule.Port -RemoteAddress '192.168.100.0/24' -ErrorAction Stop | Out-Null
        }
    }
    # Windows generated a whole-program block before its permission was granted.
    # Narrow just these generated rules; preserve blocking on every other port.
    foreach ($block in $oldBlocks) {
        $portFilter = $block | Get-NetFirewallPortFilter
        if (($portFilter.LocalPort -join ',') -ne 'Any') { continue }
        $ports = if ($portFilter.Protocol -eq 'TCP') { @('1-8842','8844-65535') } else { @('1-8843','8845-65535') }
        $portFilter | Set-NetFirewallPortFilter -LocalPort $ports -ErrorAction Stop | Out-Null
    }
    $details = foreach ($name in @('Karname-Auto-Company-HTTPS','Karname-Auto-Company-Discovery')) {
        $r = Get-NetFirewallRule -Name $name -ErrorAction Stop
        $port = $r | Get-NetFirewallPortFilter
        $address = $r | Get-NetFirewallAddressFilter
        if ($r.Enabled.ToString() -ne 'True' -or $r.Action.ToString() -ne 'Allow') { throw 'The network rule is not active.' }
        [pscustomobject]@{name=$name;protocol=$port.Protocol;port=$port.LocalPort;remote=$address.RemoteAddress}
    }
    [IO.File]::WriteAllText($ResultPath,(@{succeeded=$true;rules=@($details);firewall_disabled=$false;scope='192.168.100.0/24'} | ConvertTo-Json -Depth 5),$utf8)
} catch {
    [IO.File]::WriteAllText($ResultPath,(@{succeeded=$false;error=$_.Exception.Message;firewall_disabled=$false} | ConvertTo-Json),$utf8)
    exit 1
}
