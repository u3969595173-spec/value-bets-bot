# Backup del main.py original
Copy-Item main.py main.py.backup_before_autofill
Write-Host " Backup creado: main.py.backup_before_autofill" -ForegroundColor Green

# Leer archivos
$mainLines = Get-Content main.py
$newFunction = Get-Content main_handler_replacement.py -Raw

# Encontrar inicio y fin de la función actual
$startLine = -1
$endLine = -1
$braceCount = 0
$inFunction = $false

for ($i = 0; $i -lt $mainLines.Count; $i++) {
    $line = $mainLines[$i]
    
    # Encontrar inicio
    if ($line -match "^async def cita_disponible_handler") {
        $startLine = $i
        $inFunction = $true
        Write-Host " Función encontrada en línea $($i + 1)" -ForegroundColor Cyan
    }
    
    # Encontrar fin (siguiente función async def o class)
    if ($inFunction -and $i -gt $startLine -and ($line -match "^async def " -or $line -match "^def " -or $line -match "^class ")) {
        $endLine = $i - 1
        break
    }
}

if ($startLine -eq -1) {
    Write-Host " No se encontró la función cita_disponible_handler" -ForegroundColor Red
    exit 1
}

# Buscar línea vacía antes de la siguiente función
while ($endLine -gt $startLine -and $mainLines[$endLine] -match "^\s*$") {
    $endLine--
}

Write-Host " Rango de función: líneas $($startLine + 1) a $($endLine + 1)" -ForegroundColor Yellow

# Construir nuevo main.py
$newMainLines = @()

# Agregar líneas antes de la función
$newMainLines += $mainLines[0..($startLine - 1)]

# Agregar nueva función (extraer solo el código, sin comentarios de instrucciones)
$functionCode = $newFunction -split "`n" | Where-Object { 
    $_ -notmatch "^#.*INSTRUCCIONES" -and 
    $_ -notmatch "^Esta versión:" -and
    $_ -notmatch "^- Intenta" -and
    $_ -notmatch "^- Si falla" -and
    $_ -notmatch "^- Funciona" -and
    $_ -notmatch "^1\. Agregar import" -and
    $_ -notmatch "^2\. Reemplazar" -and
    $_ -notmatch '^\s*"""$'
}

# Encontrar donde empieza realmente la función
$functionStart = $functionCode | Select-Object -First 200 | Where-Object { $_ -match "^async def cita_disponible_handler" }
$functionStartIndex = [array]::IndexOf($functionCode, $functionStart[0])

if ($functionStartIndex -ge 0) {
    $newMainLines += $functionCode[$functionStartIndex..($functionCode.Length - 1)]
} else {
    Write-Host " Usando función completa del archivo" -ForegroundColor Yellow
    $newMainLines += $functionCode
}

# Agregar líneas después de la función
$newMainLines += ""
$newMainLines += ""
$newMainLines += $mainLines[($endLine + 1)..($mainLines.Count - 1)]

# Guardar nuevo main.py
$newMainLines | Set-Content main.py -Encoding UTF8

Write-Host " main.py actualizado correctamente" -ForegroundColor Green
Write-Host " Función cita_disponible_handler reemplazada" -ForegroundColor Green
Write-Host " Backup disponible en: main.py.backup_before_autofill" -ForegroundColor Cyan
