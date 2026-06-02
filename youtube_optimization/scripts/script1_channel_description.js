// ============================================================
// EVTRIX - YOUTUBE STUDIO OTOMATİK DOLDURMA SCRİPTLERİ
// ============================================================
// NASIL KULLANILIR:
// 1. İlgili YouTube Studio sayfasını aç
// 2. F12 tuşuna bas (DevTools açılır)
// 3. "Console" sekmesine tıkla
// 4. Aşağıdaki ilgili scripti kopyala ve yapıştır, Enter'a bas
// ============================================================


// ============================================================
// SCRIPT 1: KANAL AÇIKLAMASI
// Sayfa: https://www.youtube.com/account_customization
// ============================================================

(function() {
  var desc = `EvTrix is your #1 source for electric vehicle reviews, EV range tests, battery technology breakdowns, and the future of AI-powered transportation.

We test EVs so you don't have to — real data, real range, real results.
AI + Robotics + Electric Vehicles = The future we cover every week.
From Tesla to BYD, Rivian to Lucid — no brand bias, only truth.

What you'll find here:
✔ EV Range Tests (real-world, not EPA estimates)
✔ Battery Technology Explained (simply)
✔ AI in Transportation — what's actually happening
✔ EV comparisons, charging costs, and hidden truths
✔ Autonomous vehicles and robotics updates

Business: evtrix.contact@gmail.com

Subscribe and hit the bell — we post every week.

#ElectricVehicles #EVReview #BatteryTechnology #AITech #FutureOfTransport`;

  // Açıklama alanını bul ve doldur
  var textareas = document.querySelectorAll('textarea, [contenteditable="true"]');
  var found = false;
  textareas.forEach(function(el) {
    if (el.offsetHeight > 50) {
      el.focus();
      el.select && el.select();
      document.execCommand('selectAll', false, null);
      document.execCommand('insertText', false, desc);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      found = true;
      console.log('✅ Açıklama alanı dolduruldu! Şimdi YAYINLA butonuna tıkla.');
    }
  });
  if (!found) console.log('❌ Alan bulunamadı. Sayfanın tamamen yüklendiğinden emin ol.');
})();
