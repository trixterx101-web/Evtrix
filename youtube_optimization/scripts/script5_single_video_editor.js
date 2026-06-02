// ============================================================
// SCRIPT 5: TEK VİDEO DÜZENLEME YARDIMCISI
// Her video düzenleme sayfasında çalıştır
// Sayfa: Videoyu aç > Düzenle > F12 > Console > Yapıştır
// ============================================================

(function() {
  var tags = [
    'electric vehicles', 'EV review', 'electric cars', 'EV range test',
    'battery technology', 'AI technology', 'EV tech', 'Tesla', 'BYD',
    'Rivian', 'Lucid Motors', 'electric car range', 'EV battery life',
    'fast charging EV', 'EV charging cost', 'electric mobility',
    'autonomous vehicles', 'electric future', 'EV trends', 'Evtrix',
    'electric vehicle review', 'AI robotics', 'self driving cars',
    'clean energy', 'EV charging', 'smart transportation'
  ];

  // Sayfa URL'inden hangi video olduğunu anla
  var url = window.location.href;
  console.log('📍 Mevcut Sayfa: ' + url);

  // Başlık alanını bul
  var titleField = document.querySelector('#title-textarea textarea, input[aria-label*="title"], textarea[aria-label*="title"]');
  if (titleField) {
    console.log('✅ Başlık alanı bulundu. Mevcut başlık: ' + titleField.value);
    console.log('📝 Yeni başlığı manuel gir ve ardından tags bölümünü doldur.');
  }

  // Tags alanını bul ve doldur
  var tagInput = document.querySelector('#tags-container input, input[aria-label*="tag"], input[placeholder*="tag"]');
  if (tagInput) {
    var addTag = function(tag) {
      tagInput.focus();
      tagInput.value = tag;
      tagInput.dispatchEvent(new Event('input', { bubbles: true }));
      tagInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
      tagInput.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', keyCode: 13, bubbles: true }));
    };

    var delay = 0;
    tags.forEach(function(tag) {
      setTimeout(function() { addTag(tag); }, delay);
      delay += 200;
    });

    setTimeout(function() {
      console.log('✅ ' + tags.length + ' adet tag eklendi!');
      console.log('Şimdi başlığı değiştir ve KAYDET butonuna tıkla.');
    }, delay + 500);
  } else {
    console.log('⚠️ Tags alanı bulunamadı.');
    console.log('📋 Eklenecek taglar:');
    console.log(tags.join(', '));
  }

  // Video başlık eşleştirme rehberi
  console.log('\n📖 BAŞLIK DEĞİŞTİRME REHBERİ:');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  var titleChanges = [
    ['AMR Revolution / 500 Miles', 'AMR Robots Just Changed EVs Forever — 500 Miles Is Only the Beginning'],
    ['EV Future / AI Reveals', 'AI Analyzed 34M EV Data Points — The Results Will Shock You'],
    ['Nobody Is Talking About', 'This EV Technology Will Be Everywhere in 2 Years (Nobody Is Warning You)'],
    ['Replace Human Drivers', 'EV Robots Will Replace Human Drivers by 2026 — Here\'s the Proof'],
    ['AI Predict EV Range', 'I Let AI Predict My EV Range for 30 Days — It Was Wrong Once'],
    ['Wireless Charging SCAM', 'We Tested Wireless EV Charging — $3,000 and 85% Efficiency (Worth It?)']
  ];
  titleChanges.forEach(function(change) {
    console.log('  [' + change[0] + ']\n  → ' + change[1] + '\n');
  });
})();
