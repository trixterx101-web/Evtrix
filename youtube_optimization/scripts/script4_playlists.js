// ============================================================
// SCRIPT 4: PLAYLİST OLUŞTURUCU
// Sayfa: https://studio.youtube.com/channel/UCqESu_JRhmaUIvROLu0kGEQ/playlists
// F12 > Console > Yapıştır > Enter
// ============================================================

(function() {
  var playlists = [
    {
      title: 'EV Range Tests — Real World Data',
      description: 'Real-world EV range tests — not EPA estimates. We drive in real conditions: winter, highway, city, heat. Every test includes raw data, charging costs, and honest results. No sponsored content. #EVRange #ElectricVehicles #EVReview'
    },
    {
      title: 'Battery Technology Explained',
      description: 'Everything you need to know about EV batteries — explained simply. Battery degradation, charging strategies, fast charging myths, real lifespan data. This playlist could save your battery. #BatteryTechnology #EVBattery #ElectricCars'
    },
    {
      title: 'AI and Robotics in EVs',
      description: 'AI is transforming electric vehicles faster than anyone realizes. AMR robots, autonomous delivery, AI range prediction, self-driving updates — all the data, none of the hype. #AITech #Robotics #AutonomousVehicles'
    },
    {
      title: 'EV Tech You Dont Know About',
      description: 'The EV technologies that mainstream media ignores. Wireless charging, V2G, solid-state batteries, new motor tech — the future is closer than you think. #EVTech #FutureOfTransport #ElectricFuture'
    },
    {
      title: 'EV Cost and Value Breakdowns',
      description: 'Is an EV actually cheaper to own? We do the real math. Purchase price, charging costs, maintenance, depreciation, insurance — all the numbers you need before buying. #EVCost #ElectricCars #EVvsGas'
    },
    {
      title: 'EvTrix Best Of — Start Here',
      description: 'New to EvTrix? Start here. Our most-watched, most data-driven videos on EVs, AI, and the future of transportation. Subscribe for weekly updates — we never post opinions without data. #EvTrix #ElectricVehicles'
    }
  ];

  console.log('📋 OLUŞTURULACAK 6 PLAYLİST:');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  playlists.forEach(function(pl, i) {
    console.log('\n' + (i+1) + '. 📁 ' + pl.title);
    console.log('   Açıklama: ' + pl.description);
  });
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('👆 "Yeni oynatma listesi" butonuna tıkla ve yukarıdaki her playlist için ayrı ayrı oluştur.');
  console.log('Her playlist için: Başlığı yaz > Açıklamayı yapıştır > Herkese açık seç > Oluştur');

  // "Yeni oynatma listesi" butonunu bulmaya çalış
  var newBtn = document.querySelector('[aria-label*="playlist"], button[aria-label*="Create"], ytcp-button');
  if (newBtn) {
    console.log('\n✅ Buton bulundu! Otomatik tıklanıyor...');
    newBtn.click();
  } else {
    console.log('\n⚠️ Buton otomatik bulunamadı — "Yeni oynatma listesi" butonuna manuel tıkla.');
  }
})();
