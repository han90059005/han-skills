param(
    [Parameter(Mandatory = $true)]
    [string]$DocxPath,
    [string]$TemplatePath = "D:\Desktop\GraduationThesis\.agents\skills\thesis-md-to-word\assets\reference.docx"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $DocxPath)) {
    throw "DOCX not found: $DocxPath"
}

$wdHeaderFooterPrimary = 1
$wdHeaderFooterFirstPage = 2
$wdHeaderFooterEvenPages = 3
$wdPageNumberStyleArabic = 0
$wdPageNumberStyleLowercaseRoman = 2
$wdFormatXMLDocument = 16
$wdAlignParagraphLeft = 0
$wdAlignParagraphCenter = 1
$wdAlignParagraphRight = 2
$wdLineSpaceSingle = 0
$wdNumberGallery = 2
$wdListApplyToWholeList = 0
$wdWord10ListBehavior = 2

$word = $null
$doc = $null
$templateDoc = $null
$saveCopyPath = $null

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0

    $doc = $word.Documents.Open($DocxPath, $false, $false)
    $templateDoc = $word.Documents.Open($TemplatePath, $false, $true)

    foreach ($section in $doc.Sections) {
        foreach ($kind in @($wdHeaderFooterPrimary, $wdHeaderFooterFirstPage, $wdHeaderFooterEvenPages)) {
            $section.Headers.Item($kind).Range.FormattedText = $templateDoc.Sections.Item(1).Headers.Item($kind).Range.FormattedText
        }
    }

    for ($i = 1; $i -le $doc.OMaths.Count; $i++) {
        $doc.OMaths.Item($i).Range.Font.Size = 14
        $doc.OMaths.Item($i).Range.Font.Name = "Times New Roman"
        $doc.OMaths.Item($i).Range.Font.NameFarEast = "SimSun"
    }

    foreach ($table in $doc.Tables) {
        if ($table.Rows.Count -eq 1 -and $table.Columns.Count -eq 2) {
            $rightText = ""
            try { $rightText = [string]$table.Cell(1, 2).Range.Text } catch {}
            $rightText = $rightText -replace "[`r`a]", ""
            if ($rightText -match "^\(\d+-\d+\)$") {
                $table.Cell(1, 1).Range.ParagraphFormat.Alignment = $wdAlignParagraphCenter
                $table.Cell(1, 2).Range.ParagraphFormat.Alignment = $wdAlignParagraphRight
                $table.Cell(1, 2).Range.Font.Name = "Times New Roman"
                $table.Cell(1, 2).Range.Font.NameFarEast = "SimSun"
                $table.Cell(1, 2).Range.Font.Size = 12
            }
        }
    }

    $referenceStarts = @()
    $referenceEnds = @()
    foreach ($para in $doc.Paragraphs) {
        $styleName = ""
        try { $styleName = [string]$para.Range.Style.NameLocal } catch {}
        $paraText = ""
        try { $paraText = ([string]$para.Range.Text) -replace "[`r`a]", "" } catch {}
        $paraText = $paraText.Trim()
        $para.SpaceBefore = 0
        $para.SpaceAfter = 0
        if ($paraText -match "^\[\d+\]") {
            try { $para.Range.ListFormat.RemoveNumbers() } catch {}
            $marker = [regex]::Match($paraText, "^\[\d+\]\s*")
            if ($marker.Success) {
                $markerRange = $para.Range.Duplicate
                $markerRange.SetRange($para.Range.Start, $para.Range.Start + $marker.Value.Length)
                $markerRange.Delete()
            }
            $para.Alignment = $wdAlignParagraphLeft
            $para.LineSpacingRule = $wdLineSpaceSingle
            $para.LeftIndent = 0
            $para.FirstLineIndent = 0
            try { $para.TabStops.ClearAll() } catch {}
            $para.Range.Font.Name = "Times New Roman"
            $para.Range.Font.NameFarEast = "SimSun"
            $para.Range.Font.Size = 12
            $para.Range.Font.Bold = 0
            $referenceStarts += $para.Range.Start
            $referenceEnds += $para.Range.End
            continue
        }
        if ($styleName -match "Source Code|Code") {
            $para.Range.Font.Name = "Times New Roman"
            $para.Range.Font.NameFarEast = "SimSun"
            $para.Range.Font.Size = 12
            $para.Range.Font.Bold = 0
            for ($c = 1; $c -le $para.Range.Characters.Count; $c++) {
                $charFont = $para.Range.Characters.Item($c).Font
                $charFont.Name = "Times New Roman"
                $charFont.NameFarEast = "SimSun"
                $charFont.Bold = 0
            }
            $para.LeftIndent = 24
        }
    }

    if ($referenceStarts.Count -gt 0) {
        $refStart = [int](($referenceStarts | Measure-Object -Minimum).Minimum)
        $refEnd = [int](($referenceEnds | Measure-Object -Maximum).Maximum)
        $refRange = $doc.Range($refStart, $refEnd)
        $listTemplate = $word.ListGalleries.Item($wdNumberGallery).ListTemplates.Item(1)
        $level = $listTemplate.ListLevels.Item(1)
        $level.NumberFormat = "[%1]"
        $level.NumberStyle = 0
        $level.NumberPosition = 0
        $level.Alignment = $wdAlignParagraphLeft
        $level.TextPosition = 0
        $level.TabPosition = 0
        $level.TrailingCharacter = 1
        $level.StartAt = 1
        $refRange.ListFormat.ApplyListTemplateWithLevel(
            $listTemplate,
            $false,
            $wdListApplyToWholeList,
            $wdWord10ListBehavior,
            1
        )
        foreach ($para in $refRange.Paragraphs) {
            $para.Alignment = $wdAlignParagraphLeft
            $para.LineSpacingRule = $wdLineSpaceSingle
            $para.SpaceBefore = 0
            $para.SpaceAfter = 0
            $para.LeftIndent = 0
            $para.FirstLineIndent = 0
            try { $para.TabStops.ClearAll() } catch {}
            $para.Range.Font.Name = "Times New Roman"
            $para.Range.Font.NameFarEast = "SimSun"
            $para.Range.Font.Size = 12
            $para.Range.Font.Bold = 0
        }
    }

    if ($doc.Sections.Count -ge 2) {
        $doc.Sections.Item(1).Footers.Item($wdHeaderFooterPrimary).PageNumbers.RestartNumberingAtSection = $true
        $doc.Sections.Item(1).Footers.Item($wdHeaderFooterPrimary).PageNumbers.StartingNumber = 1
        $doc.Sections.Item(1).Footers.Item($wdHeaderFooterPrimary).PageNumbers.NumberStyle = $wdPageNumberStyleLowercaseRoman

        for ($s = 2; $s -le $doc.Sections.Count; $s++) {
            $footer = $doc.Sections.Item($s).Footers.Item($wdHeaderFooterPrimary).PageNumbers
            $footer.RestartNumberingAtSection = $true
            $footer.StartingNumber = 1
            $footer.NumberStyle = $wdPageNumberStyleArabic
        }
    } else {
        $footer = $doc.Sections.Item(1).Footers.Item($wdHeaderFooterPrimary).PageNumbers
        $footer.RestartNumberingAtSection = $true
        $footer.StartingNumber = 1
        $footer.NumberStyle = $wdPageNumberStyleArabic
    }

    $docDir = Split-Path -Parent $DocxPath
    $docBase = [System.IO.Path]::GetFileNameWithoutExtension($DocxPath)
    $saveCopyPath = Join-Path $docDir ($docBase + ".__codex_save__.docx")
    if (Test-Path -LiteralPath $saveCopyPath) {
        Remove-Item -LiteralPath $saveCopyPath -Force
    }
    $doc.SaveAs2($saveCopyPath, $wdFormatXMLDocument)
    $doc.Close($false)
    $doc = $null
    $templateDoc.Close($false)
    $templateDoc = $null
    Write-Output ("POSTPROCESS_OUTPUT=" + $saveCopyPath)
    $saveCopyPath = $null
}
finally {
    if ($templateDoc -ne $null) {
        try { $templateDoc.Close($false) } catch {}
    }
    if ($doc -ne $null) {
        try { $doc.Close($false) } catch {}
    }
    if ($word -ne $null) {
        try { $word.Quit() } catch {}
    }
    if ($saveCopyPath -ne $null -and (Test-Path -LiteralPath $saveCopyPath)) {
        try { Remove-Item -LiteralPath $saveCopyPath -Force } catch {}
    }
}
