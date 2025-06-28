# Deploy Message Status to ECR using AWS Tools for PowerShell
param(
    [string]$AccountId = "814029820850",
    [string]$Region = "ap-southeast-1",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

# Set working directory to script location
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptPath
Write-Host "Working directory: $ScriptPath" -ForegroundColor Cyan

# Set variables
$RepositoryName = "message-status"
$RepositoryUri = "${AccountId}.dkr.ecr.${Region}.amazonaws.com/${RepositoryName}"
$ImageUri = "${RepositoryUri}:${ImageTag}"

Write-Host "開始 Starting deployment of Message Status to ECR using AWS Tools for PowerShell..." -ForegroundColor Green
Write-Host "Account ID: $AccountId" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "Repository: $RepositoryUri" -ForegroundColor Yellow
Write-Host "Image URI: $ImageUri" -ForegroundColor Yellow

# 0. Check prerequisites
Write-Host "0. Checking prerequisites..." -ForegroundColor Blue

# Check Docker
try {
    docker version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is not running"
    }
    Write-Host "✓ Docker is running" -ForegroundColor Green
}
catch {
    Write-Host "✗ Docker check failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Please ensure Docker Desktop is installed and running" -ForegroundColor Yellow
    exit 1
}

# Check AWS Tools for PowerShell
try {
    Import-Module AWSPowerShell.NetCore -ErrorAction Stop
    Write-Host "✓ AWS Tools for PowerShell is available" -ForegroundColor Green
}
catch {
    Write-Host "✗ AWS Tools for PowerShell not found" -ForegroundColor Red
    Write-Host "Please install AWS Tools for PowerShell:" -ForegroundColor Yellow
    Write-Host "  Install-Module -Name AWSPowerShell.NetCore -Force" -ForegroundColor Yellow
    exit 1
}

# 1. Authenticate Docker client to ECR
Write-Host "1. Authenticating Docker client to ECR..." -ForegroundColor Blue
try {
    # Set AWS region for the session
    Set-DefaultAWSRegion -Region $Region
    
    # Get ECR login command and authenticate
    $loginPassword = (Get-ECRLoginCommand).Password
    $loginPassword | docker login --username AWS --password-stdin $RepositoryUri
    
    if ($LASTEXITCODE -ne 0) {
        throw "Docker login to ECR failed"
    }
    
    Write-Host "✓ ECR authentication successful" -ForegroundColor Green
}
catch {
    Write-Host "✗ ECR authentication failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Please ensure:" -ForegroundColor Yellow
    Write-Host "  1. AWS credentials are configured" -ForegroundColor Yellow
    Write-Host "  2. You have ECR permissions" -ForegroundColor Yellow
    Write-Host "  3. AWS Tools for PowerShell is up to date" -ForegroundColor Yellow
    exit 1
}

# 2. Check and create ECR repository
Write-Host "2. Checking ECR repository..." -ForegroundColor Blue
try {
    Get-ECRRepository -RepositoryName $RepositoryName -Region $Region | Out-Null
    Write-Host "✓ ECR repository exists" -ForegroundColor Green
}
catch {
    Write-Host "Creating ECR repository..." -ForegroundColor Yellow
    try {
        New-ECRRepository -RepositoryName $RepositoryName -Region $Region | Out-Null
        Write-Host "✓ ECR repository created successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "✗ ECR repository creation failed: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

# 3. Build Docker image
Write-Host "3. Building Docker image..." -ForegroundColor Blue

# Check if Dockerfile exists
if (-not (Test-Path "Dockerfile")) {
    Write-Host "✗ Dockerfile not found in current directory: $(Get-Location)" -ForegroundColor Red
    Write-Host "Please ensure you're running this script from the correct directory" -ForegroundColor Yellow
    exit 1
}

try {
    Write-Host "Running: docker build -t $RepositoryName ." -ForegroundColor Cyan
    docker build -t $RepositoryName .
    
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed"
    }
    
    Write-Host "✓ Docker image built successfully" -ForegroundColor Green
}
catch {
    Write-Host "✗ Docker image build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 4. Tag image
Write-Host "4. Tagging image..." -ForegroundColor Blue
try {
    Write-Host "Running: docker tag ${RepositoryName}:latest $ImageUri" -ForegroundColor Cyan
    docker tag "${RepositoryName}:latest" $ImageUri
    
    if ($LASTEXITCODE -ne 0) {
        throw "Docker tag failed"
    }
    
    Write-Host "✓ Image tagged successfully: $ImageUri" -ForegroundColor Green
}
catch {
    Write-Host "✗ Image tagging failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 5. Push image to ECR
Write-Host "5. Pushing image to ECR..." -ForegroundColor Blue
try {
    Write-Host "Running: docker push $ImageUri" -ForegroundColor Cyan
    docker push $ImageUri
    
    if ($LASTEXITCODE -ne 0) {
        throw "Docker push failed"
    }
    
    Write-Host "✓ Image pushed successfully!" -ForegroundColor Green
}
catch {
    Write-Host "✗ Image push failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🎉 Deployment completed successfully!" -ForegroundColor Green
Write-Host "📦 Image successfully pushed to: $ImageUri" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 You can now use this image in your ECS task definition." -ForegroundColor Yellow

# Optional: Display image information
Write-Host ""
Write-Host "📋 Image Information:" -ForegroundColor Blue
try {
    $repoInfo = Get-ECRRepository -RepositoryName $RepositoryName -Region $Region
    Write-Host "Repository URI: $($repoInfo.RepositoryUri)" -ForegroundColor Cyan
    Write-Host "Registry ID: $($repoInfo.RegistryId)" -ForegroundColor Cyan
    Write-Host "Created: $($repoInfo.CreatedAt)" -ForegroundColor Cyan
}
catch {
    Write-Host "Could not retrieve repository information" -ForegroundColor Yellow
}
