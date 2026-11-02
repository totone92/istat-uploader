# Firma con eSigner di SSL.com i file passati, sul posto, con marca temporale.
#
#   powershell -File scripts\firma.ps1 dist\IstatUploader.exe
#
# Lo chiamano la ricetta PyInstaller (i binari interni), il giro di GitHub (l'.exe) e Inno
# Setup (disinstallatore e installer). Credenziali e cartella di CodeSignTool arrivano
# dall'ambiente, mai dagli argomenti di chi chiama: vedi BUILD_WINDOWS.md, «La firma».
param([Parameter(Mandatory, ValueFromRemainingArguments)][string[]]$File)
$ErrorActionPreference = "Stop"
# Lanciato da pwsh eredita i suoi moduli, e Get-AuthenticodeSignature non si carica.
$env:PSModulePath = [Environment]::GetEnvironmentVariable("PSModulePath", "Machine")

$utente = $env:ESIGNER_USERNAME
$chiave = $env:ESIGNER_PASSWORD
$credenziale = $env:ESIGNER_CREDENTIAL_ID
$totp = $env:ESIGNER_TOTP_SECRET
$cartella = $env:CODESIGNTOOL_DIR
if (-not ($utente -and $chiave -and $credenziale -and $totp -and $cartella)) {
    throw "firma: mancano le credenziali o CODESIGNTOOL_DIR"
}
# Il JDK 11.0.2 dentro CodeSignTool non riconosce il certificato TLS di SSL.com: si usa
# quello della macchina di GitHub, se c'è.
$java = Join-Path $cartella "jdk-11.0.2\bin\java.exe"
if ($env:JAVA_HOME_17_X64) { $java = Join-Path $env:JAVA_HOME_17_X64 "bin\java.exe" }
$jar = Get-ChildItem (Join-Path $cartella "jar\code_sign_tool-*.jar") | Select-Object -First 1

# CodeSignTool cerca conf\ nella cartella corrente, e può uscire con 0 anche dopo un errore:
# fa fede la firma che si trova nel file. Ogni file è un tentativo con un codice TOTP suo,
# quindi un rifiuto si riprova solo a codice cambiato (30 secondi).
foreach ($voce in $File) {
    $originale = (Resolve-Path -LiteralPath $voce).Path
    # CodeSignTool guarda l'estensione: rifiuta i .pyd e i temporanei di Inno Setup, che sono
    # PE come gli altri. Si firmano col nome da .dll e poi tornano al loro.
    $percorso = $originale
    if ([IO.Path]::GetExtension($originale) -notin ".exe", ".dll") {
        $percorso = "$originale.firma.dll"
        Move-Item -LiteralPath $originale $percorso
    }
    $firmato = $false
    foreach ($tentativo in 1..3) {
        Push-Location $cartella
        try {
            $ErrorActionPreference = "Continue"
            & $java -Xmx1024M -jar $jar.FullName sign "-username=$utente" "-password=$chiave" `
                "-credential_id=$credenziale" "-totp_secret=$totp" `
                "-input_file_path=$percorso" "-override=true" 2>&1 | ForEach-Object { "$_" }
            $ErrorActionPreference = "Stop"
        } finally {
            Pop-Location
        }
        if ((Get-AuthenticodeSignature -LiteralPath $percorso).Status -ne "NotSigned") {
            $firmato = $true
            break
        }
        if ($tentativo -lt 3) { Start-Sleep -Seconds 31 }
    }
    if ($percorso -ne $originale) { Move-Item -LiteralPath $percorso $originale }
    if (-not $firmato) { throw "firma non riuscita: $originale" }
    "firmato: $originale"
}
