// ============================================================
// SCRIPT 2: VİDEO BAŞLIKLARINI OPTİMİZE ET
// Sayfa: https://studio.youtube.com/channel/UCqESu_JRhmaUIvROLu0kGEQ/videos
// F12 > Console > Yapıştır > Enter
// ============================================================

(function() {
  var titleMap = {
    'AMR Revolution': 'AMR Robots Just Changed EVs Forever — 500 Miles Is Only the Beginning',
    '500 Miles Is Just': 'AMR Robots Just Changed EVs Forever — 500 Miles Is Only the Beginning',
    'EV Future Is Not': 'AI Analyzed 34M EV Data Points — The Results Will Shock You',
    'AI Reveals': 'AI Analyzed 34M EV Data Points — The Results Will Shock You',
    'Nobody Is Talking': 'This EV Technology Will Be Everywhere in 2 Years (Nobody Is Warning You)',
    'EV Tech Nobody': 'This EV Technology Will Be Everywhere in 2 Years (Nobody Is Warning You)',
    'Replace Human Drivers': 'EV Robots Will Replace Human Drivers by 2026 — Here\'s the Proof',
    'EV Robots Are About': 'EV Robots Will Replace Human Drivers by 2026 — Here\'s the Proof',
    'AI Predict My EV Range': 'I Let AI Predict My EV Range for 30 Days — It Was Wrong Once',
    'Result Was Shocking': 'I Let AI Predict My EV Range for 30 Days — It Was Wrong Once',
    'Wireless EV Charging': 'We Tested Wireless EV Charging — $3,000 and 85% Efficiency (Worth It?)',
    'SCAM': 'We Tested Wireless EV Charging — $3,000 and 85% Efficiency (Worth It?)'
  };

  var tags = 'electric vehicles, EV review, electric cars, EV range test, battery technology, AI technology, EV tech, Tesla, BYD, Rivian, Lucid Motors, electric car range, EV battery life, fast charging EV, EV charging cost, electric mobility, autonomous vehicles, electric future, EV trends, Evtrix';

  // Video başlıklarını bul
  var videoRows = document.querySelectorAll('ytcp-video-list-cell-title, #video-title, .title');
  var count = 0;

  videoRows.forEach(function(el) {
    var currentTitle = el.innerText || el.textContent || '';
    Object.keys(titleMap).forEach(function(key) {
      if (currentTitle.includes(key)) {
        console.log('🎯 Bulunan video: ' + currentTitle);
        console.log('✅ Yeni başlık: ' + titleMap[key]);
        count++;
      }
    });
  });

  if (count === 0) {
    console.log('⚠️ Video başlıkları bu sayfada görünmüyor.');
    console.log('📋 Manuel olarak yapılacaklar:');
    Object.keys(titleMap).forEach(function(key) {
      console.log('  "' + key + '" içeren video → ' + titleMap[key]);
    });
  }

  console.log('\n📌 Her video için eklenecek TAGS:\n' + tags);
  console.log('\n📖 Talimat: Her videoyu aç > başlığı değiştir > tags ekle > KAYDET');
})();
