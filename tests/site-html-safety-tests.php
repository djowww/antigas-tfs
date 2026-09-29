<?php
declare(strict_types=1);

require __DIR__ . '/../deploy/site-public/i18n.php';
$GLOBALS['antigasLanguage'] = 'en';

$input = '<strong onclick="alert(1)">Safe</strong><em style="background:url(javascript:alert(1))"> text</em><br class="x">tail<img src=x onerror="alert(2)">';
$expected = '<strong>Safe</strong><em> text</em><br>tail';
$actual = siteTHtml($input);
if ($actual !== $expected) {
    fwrite(STDERR, "siteTHtml did not reduce allowed markup to bare tags.\nExpected: $expected\nActual: $actual\n");
    exit(1);
}

echo "Site HTML safety regression passed\n";
