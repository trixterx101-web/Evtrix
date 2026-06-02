// ============================================================
// SCRIPT 3: YÜKLEME VARSAYILANLARI
// Sayfa: YouTube Studio > Ayarlar > Yükleme varsayılanları
// (Ayarlar dişli ikonu sol altta)
// F12 > Console > Yapıştır > Enter
// ============================================================

(function() {
  var defaultDesc = `[Video özeti buraya yazılacak]

━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ CHAPTERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━
0:00 — Intro

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 MORE FROM EVTRIX
━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶ Subscribe: https://youtube.com/@EvTrix

🔔 Real EV data, every week. Subscribe & hit the bell!

#ElectricVehicles #EVReview #EVTech #BatteryTechnology #AITech #Tesla #BYD #Rivian #LucidMotors #ElectricCars #EVRange #FutureOfTransport #SelfDriving #AutonomousVehicles #CleanEnergy #EVCharging #ElectricFuture #EVTrends #SmartTransportation #Robotics`;

  // Tüm textarea ve contenteditable alanları bul
  var allFields = document.querySelectorAll('textarea, [contenteditable="true"]');
  var filled = 0;

  allFields.forEach(function(el) {
    // Açıklama alanını tespit et (yüksekliği büyük olan)
    if (el.offsetHeight > 80 || (el.getAttribute('aria-label') || '').toLowerCase().includes('description')) {
      el.focus();
      document.execCommand('selectAll', false, null);
      document.execCommand('insertText', false, defaultDesc);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      filled++;
      console.log('✅ Yükleme varsayılanı açıklama alanı dolduruldu!');
    }
  });

  if (filled === 0) {
    console.log('⚠️ Alan otomatik doldurulamadı. Manuel yapıştırma gerekli:');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log(defaultDesc);
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('Yukarıdaki metni kopyala ve Açıklama alanına yapıştır.');
  } else {
    console.log('Şimdi KAYDET butonuna tıkla!');
  }
})();
