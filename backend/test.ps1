function Start-Dev { Write-Host "IT WORKED" }
switch ($args[0]) {
    "start" { Start-Dev }
    default { Write-Host "default hit" }
}
