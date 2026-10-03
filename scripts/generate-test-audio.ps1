param([string]$OutputPath = (Join-Path $PSScriptRoot '..\.runtime\test-recording.wav'))
$ErrorActionPreference = 'Stop'
$target = [System.IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.Rate = -2
$voice.SetOutputToWaveFile($target)
$script = @'
This is a sample recording for testing the Suno audio notes application. Today we are planning a small community garden. The garden will have vegetables, herbs, and a place for children to learn about plants. We have three priorities. First, we need to understand which plants will grow well in our climate. Second, we need a simple watering schedule. Third, we need to invite volunteers from the neighborhood.
Maya will prepare a list of seeds by Friday. Ravi will check the water supply and measure the available space. We decided to start with tomatoes, spinach, basil, and mint. These plants are familiar to most families and should be useful in everyday cooking. We will not buy expensive equipment during the first month. Instead, we will borrow tools and reuse containers wherever possible.
The budget for the pilot is five thousand rupees. Half of this will be reserved for soil and compost. The remaining amount will cover seeds, basic tools, and signs. We have not decided on an opening date yet. That depends on the weather and the availability of volunteers. The next planning session will be on Saturday morning, when everyone can look at the site together.
There is one important concern. The garden must remain accessible to older residents and people who have difficulty walking. We should keep the main path clear and provide a few raised beds. We also want to label every plant with its name and basic care instructions. The goal is to make the garden welcoming and easy to maintain. We will review what worked after the first month and adjust the plan based on what we learn.
'@
$voice.Speak($script)
$voice.Dispose()
Write-Output "Created synthetic sample audio: $target"
