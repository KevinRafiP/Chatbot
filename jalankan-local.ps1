# Membaca NGROK_PATH, NGROK_DOMAIN, dan GERBANG_LOCAL_PORT dari backend\.env, lalu menjalankan gerbang local dan ngrok
$isiEnv = @{}
Get-Content "$PSScriptRoot\backend\.env" | Where-Object { $_ -match '^\s*([^#=]+)=(.*)$' } | ForEach-Object { $isiEnv[$Matches[1].Trim()] = $Matches[2].Trim() }
$ngrok = if ($isiEnv["NGROK_PATH"]) { $isiEnv["NGROK_PATH"] } else { "ngrok" }
$port = if ($isiEnv["GERBANG_LOCAL_PORT"]) { $isiEnv["GERBANG_LOCAL_PORT"] } else { "8090" }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\backend'; go run ./cmd/gerbang-local"
& $ngrok http --url=$($isiEnv["NGROK_DOMAIN"]) $port