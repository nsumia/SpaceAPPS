Göl Kaybı Dedektörü — Claude Code Görev Tanımı (v2)
Bu prompt'u Claude Code'a yapıştır. Proje klasöründe şu üç dosya hazır olmalı: burdur_area.py, live_data.py, app.py (eski Streamlit prototipi; yalnızca referans olarak kullanılacak).

————
0. Bağlam
NASA Space Apps Challenge 2026 hackathon'undayız. Challenge: "Be An Earth System Trend Detective!". Challenge şunu istiyor: NASA görevlerinin ölçtüğü ya da NASA modellerinin ürettiği değişkenleri bulup zaman içindeki değişimini görselleştirmek; neyin, nerede, ne kadar değiştiğini ve bu değişimin istatistiksel olarak anlamlı olup olmadığını belirlemek.
Projemiz: Göl Kaybı Dedektörü Sunum cümlesi: "Göllerimiz küçülüyor. Ama ne kadarı iklim, ne kadarı biz? Türkiye dünyanın neresinde?"
Araç her göl için şu soruları cevaplıyor:
1. Ne kadar küçüldü? 1985'ten bugüne yıllık yüzey alanı ve hacim
2. Anlamlı mı? Hamed-Rao düzeltmeli Mann-Kendall testi ve Sen eğimi
3. Ne zamandan beri? Kaybın doğal dalgalanmanın üstüne çıktığı yıl
4. Neden? Yağış eksi buharlaşma (P − E) modeliyle iklimle açıklanan kayıp ve açıklanamayan kalan kısım
5. Isınıyor mu? Göl yüzey sıcaklığı trendi
6. Şu an durum ne? NASA API'lerinden canlı veri
7. Türkiye dünyanın neresinde? Dünya genelindeki göllerle karşılaştırma. Kullanıcı haritada herhangi bir gölü ya da bölgeyi seçip analiz ettirebiliyor.
Kapsam iki halkalı:
- Halka 1 — Türkiye: Burdur, Akşehir, Eğirdir, Van. Tamamen doğrulanmış ve önceden hesaplanmış.
- Halka 2 — Küresel: Önceden hesaplanmış 12–15 referans gölü ve haritada seçilen herhangi bir göl için isteğe bağlı analiz.
Zaman kısıtı: Teslim Pazar akşamı. Halka 2'ye, Halka 1 uçtan uca çalışmadan başlama. Her aşamanın sonunda uygulama çalışır durumda olmalı. Zaman yetmezse küresel kısım yalnızca önceden hesaplanmış referans göllerle sunulur; isteğe bağlı analiz ise "beta" olarak işaretlenir.
————
1. Mevcut kod (önce bunları oku, sonra değiştir)
Dosya Ne yapıyor Durum
burdur_area.py Planetary Computer STAC üzerinden Landsat 5/8/9 C2 L2 verisi çekiyor. Ağustos–Eylül medyan kompozitinde MNDWI > eşik ile yıllık göl alanını, termal banttan kıyıdan ≥150 m uzaktaki saf su piksellerinin göl yüzey sıcaklığını hesaplıyor. Hamed-Rao Mann-Kendall + Sen eğimi uyguluyor. window_area() herhangi bir tarih aralığı için çalışıyor. Sahte veriyle test edildi. Gerçek veriyle hiç çalıştırılmadı.
live_data.py Canlı katman: Landsat (son 45 gün ve geçen yılın aynı dönemi), SWOT Hydrocron (son seviye), NASA POWER (su yılı yağışı ve 1991–2020 normali), NASA GIBS WMS (dünkü VIIRS görüntüsü). Her kaynak bağımsız; hata olursa ok=False dönüyor. Yağış mantığı sahte veriyle doğrulandı. API'ler gerçek veriyle denenmedi.
app.py Streamlit prototipi. Yeni arayüzle değiştirilecek. Yalnızca hangi bilgilerin gösterildiğine dair referans olarak kullan.
Doğrulanmamış varsayımlar (ilk iş bunları kontrol et)
1. Planetary Computer landsat-c2-l2 koleksiyonunda termal bant adı Landsat 5 için lwir, Landsat 8/9 için lwir11 olarak varsayıldı. Gerçek bir item'ın assets anahtarlarını yazdırıp doğrula.
2. Yüzey sıcaklığı ölçeği DN * 0.00341802 + 149.0 (Kelvin), yansıtım ölçeği DN * 0.0000275 - 0.2. Item'ın raster:bands metadatasıyla karşılaştır.
3. NASA POWER JSON yapısı: properties.parameter.PRECTOTCORR. Aylık uç noktada YYYY13 yıllık toplam. Eksik değer -999.
4. Hydrocron: feature=PriorLake, Accept: text/csv başlığı ve lake_id,time_str,wse,area_total alanları. Geçersiz değerler no_data ve -999999999999.
5. GIBS katmanı VIIRS_NOAA20_CorrectedReflectance_TrueColor. WMS 1.3.0 ile EPSG:4326'da BBOX sırası lat_min,lon_min,lat_max,lon_max.
6. Projeksiyon EPSG:32636 (UTM 36K) olarak sabit kodlanmış. Bu yalnızca Batı Türkiye için doğru. Van ve küresel göller için yanlış alan verir (bkz. Aşama 2).
7. LAKES sözlüğündeki kutu koordinatları ve havza noktaları yaklaşık. pld_id değerleri boş (None).
————
2. Hedef mimari
lake-detective/
├── backend/                 # Python 3.11, FastAPI
│   ├── core/                # Bilimsel çekirdek (burdur_area.py ve live_data.py'den taşınacak)
│   │   ├── landsat.py       #   window_area, yıllık seri, otomatik UTM, uyarlanabilir çözünürlük
│   │   ├── stats.py         #   Mann-Kendall, Sen, ortaya çıkış yılı, bootstrap
│   │   ├── climate.py       #   NASA POWER, P−E, ayrıştırma
│   │   ├── swot.py          #   Hydrocron, hipsometri, hacim
│   │   └── live.py          #   canlı kartlar ve önbellek
│   ├── api/                 # FastAPI router'ları
│   ├── jobs/                # Arka plan iş kuyruğu (SQLite tabanlı)
│   ├── scripts/             # precompute.py, prefetch.py, build_lake_index.py
│   └── tests/
├── frontend/                # React + Vite + TypeScript
│   └── src/ (map/, charts/, pages/, i18n/)
├── data/
│   ├── lakes/<lake_id>/     # series.json, masks/, climate.json, swot.json, meta.json
│   ├── live_cache/
│   ├── index/lakes.pmtiles  # Haritada seçilebilir göller (veya lakes.geojson)
│   └── jobs.sqlite
├── docker-compose.yml
└── README.md

Teknoloji seçimleri (gerekçe: ücretsiz, anahtarsız, hızlı kurulum):
- Backend: FastAPI + Uvicorn. Bilimsel kod Python'da kalıyor.
- Frontend: React + Vite + TypeScript.
- Harita: MapLibre GL JS (token gerektirmez).
  - Altlık: OpenFreeMap vektör stili (anahtarsız) ve NASA GIBS katmanları (Blue Marble ve günlük VIIRS gerçek renk, tarih seçilebilir).
- Grafikler: Apache ECharts (echarts-for-react). Güven bandı, işaretleme çizgileri ve zoom için uygun.
- Durum yönetimi: TanStack Query (önbellekli API çağrıları, iş durumu için polling).
- Göl indeksi: HydroLAKES (≥10 km² filtreli) ya da SWOT PLD'den üretilmiş PMTiles. Çok ağırsa ≥50 km² filtreli GeoJSON kullan.
- Üretim: docker-compose up ile tek komutta çalışmalı. FastAPI, derlenmiş frontend'i statik olarak sunsun ki demo tek porttan açılsın.
————
3. Görevler (sırayla yap, her birinin sonunda kabul kriterini doğrula)
AŞAMA 1 — Gerçek veriyle çalıştır ve doğrula (en yüksek öncelik)
- [ ] Bölüm 1'deki varsayım 1 ve 2'yi doğrula, gerekiyorsa düzelt.
- [ ] python burdur_area.py --start 2020 --end 2020, ardından tam seriyi çalıştır (1985–2025).
- Kabul kriteri: Burdur alanı 1986 civarında ~206 km², 2020–2022 arasında ~120–125 km² çıkmalı (yayımlanmış çalışmalar: Hacettepe/ESPR 2023 ve AKÜ FEMÜBİD 2020). Fark %10'dan fazlaysa sebebini bul: eşik, kutu, bulut maskesi ya da komşu göller (Yarışlı). Sonucu VALIDATION.md dosyasına yaz.
- Yaz sonu göl yüzey sıcaklığı makul bir aralıkta olmalı (Burdur için kabaca 20–28 °C).
AŞAMA 2 — Backend iskeleti ve genelleştirilmiş çekirdek
- [ ] Bölüm 2'deki yapıyı kur. burdur_area.py ve live_data.py mantığını backend/core/ altına taşı, davranışı koru.
- [ ] Otomatik UTM: Gölün merkez koordinatından UTM zonunu hesapla. Kuzey yarımkürede 326xx, güneyde 327xx. Zon sınırındaki göller için merkezi esas al. Bu yöntem çok büyük göllerde (yaklaşık 6°'den geniş) de kabul edilebilir; yine de uyarı yaz.
- [ ] Uyarlanabilir çözünürlük: Göl kutusu büyüdükçe çözünürlüğü düşür (ör. <500 km² için 30 m, <5.000 km² için 60 m, daha büyükler için 120 m). Kullanılan çözünürlüğü meta.json'a yaz. Termal maske aşındırmasını da metre cinsinden sabit tut (150 m).
- [ ] Otomatik göl poligonu: 1985–1990 MNDWI maskesinde kullanıcının seçtiği noktayı ya da poligonun merkezini içeren en büyük bağlantılı su bileşenini al ve 1 km tampon ekle. Komşu su kütleleri (ör. Akşehir için Eber, Burdur için Yarışlı) böylece dışarıda kalır.
- [ ] Havza: HydroBASINS (seviye 6–7) verisinden gölü içeren havza poligonlarını birleştir. Erişilemezse gölün etrafında tampon kullan ve bunu meta.json'da işaretle.
- [ ] Göl kayıtları data/lakes/<lake_id>/ altında dursun. lake_id formatı: varsa SWOT PLD ID, yoksa custom-<hash>.
- Kabul kriteri: python -m backend.scripts.precompute --lake burdur Aşama 1 ile aynı sonucu veriyor (±%1). Van için alan, UTM 38K ile hesaplanıyor.
AŞAMA 3 — Analizler
- [ ] Ortaya çıkış yılı (stats.py): Referans dönemi (ilk 10–15 yıl) için yıllık dalgalanmanın standart sapmasını (σ) hesapla. Trend sinyalinin (Sen doğrusu − referans ortalaması) kalıcı olarak 2σ'yı aştığı ilk yılı bul. "Kalıcı", sonraki tüm yıllarda aşılmış olması demek. Henüz ortaya çıkmadıysa "Henüz ayırt edilemiyor" döndür ve mevcut eğim ile gürültüye göre gereken tahmini yıl sayısını ver. Hem alan hem sıcaklık için uygula.
- [ ] İklim ayrıştırması (climate.py): NASA POWER aylık PRECTOTCORR ve buharlaşma verisini havza noktaları (havzadaki 4–9 nokta, havza büyüklüğüne göre) için 1981'den bugüne çek. Uygun buharlaşma parametresini POWER dokümantasyonundan doğrula. Su yılı (Ekim–Eylül; güney yarımkürede Nisan–Mart) toplamlarına çevir.
  - Model: Referans döneminde (1985–1999) yıllık alan değişimi (ΔA) ile P − E arasında doğrusal regresyon kur ve sonraki yıllar için tahmin et.
  - Gözlenen kümülatif kayıp − tahmin edilen kümülatif kayıp = iklimle açıklanamayan kayıp. Bootstrap ile %90 güven aralığı ver.
  - Arayüzde ve README'de "açıklanamayan kısım insan etkisinin kanıtı değil, işaretidir" notu yer almalı.
- [ ] SWOT hacmi (swot.py, ekstra puan): PLD ID'yi bul (PLD dosyası ya da merkeze yakın aday ID'lerle Hydrocron sorgusu). 2023'ten beri wse ve area_total çiftlerini çek, kaliteye göre filtrele. Alan → seviye eğrisi uydur, 40 yıllık Landsat alanlarına uygula ve ΔV = ∫ A dh hesapla. SWOT'un gözlediği alan aralığının dışındaki yıllar (dış değerleme) ayrı işaretlensin.
- Kabul kriteri: Birim testleri. Ortaya çıkış yılı, sentetik bir seride ±3 yıl doğrulukla bulunuyor. Ayrıştırma, "iklim sinyali + bilinen sabit çekim" içeren sentetik bir seride çekimi %20 içinde buluyor. Dört Türkiye gölü için series.json, climate.json ve (mümkünse) swot.json hazır.
AŞAMA 4 — API
Uç nokta Açıklama
GET /api/lakes Önceden hesaplanmış tüm göllerin özeti: ad, ülke, merkez, toplam kayıp %, trend %/on yıl, p, ortaya çıkış yılı, ısınma °C/on yıl, iklimle açıklanan pay, grup (turkey / reference / custom)
GET /api/lakes/{id} Tam seri: alan, sıcaklık, hacim, iklim, istatistikler, meta
GET /api/lakes/{id}/masks/{year} Yıllık su maskesi (basitleştirilmiş GeoJSON ya da PNG + bounds)
GET /api/lakes/{id}/live Canlı kartlar. Önbellek TTL'i 3 saat. API erişilemezse son başarılı sonucu stale: true ile döndür
GET /api/identify?lon=&lat= Tıklanan noktadaki gölü göl indeksinden bul (ID, ad, alan, poligon)
POST /api/analyze Gövde: {lake_id} ya da {polygon: GeoJSON}. Bir arka plan işi başlatır ve job_id döndürür. Göl zaten hesaplanmışsa doğrudan sonucu döndürür
GET /api/jobs/{job_id} İş durumu: queued / running / done / failed, ilerleme yüzdesi, işlenen yıl, hata mesajı
GET /api/compare?ids=a,b,c&metric= Karşılaştırma için normalleştirilmiş seriler: 1985–1990 ortalamasına göre % alan, sıcaklık anomalisi
- İş kuyruğu: SQLite tablosu ve tek bir işçi süreci (aynı anda en fazla 2 iş). Aynı göl için tekrarlanan istekler mevcut işe bağlansın.
- İsteğe bağlı analizde süre sınırı: Varsayılan olarak 1985'ten bugüne 5 yılda bir analiz yapılıp ön sonuç hızla gösterilsin, ardından aradaki yıllar doldurulsun (ilerledikçe güncellenen sonuç).
- Poligon için sınırlar: 20.000 km²'den büyük poligonları reddet ve kullanıcıya daha küçük bir alan seçmesini söyle.
- OpenAPI dokümantasyonu /docs adresinde açık olsun.
AŞAMA 5 — Frontend (Streamlit'in yerine)
Ana ekran: tam ekran harita ve yan panel.
- [ ] Harita (MapLibre):
  - Önceden hesaplanmış göller, trende göre renklendirilmiş işaretlerle gösterilsin: koyu kırmızı hızlı kayıp, gri anlamsız, mavi artış. İşaret boyutu göl alanına göre değişsin.
  - Göl indeksi katmanı yakınlaştırınca görünsün. Göl poligonuna tıklayınca seçilsin.
  - Bölge seçimi: Kullanıcı haritada (a) bir göle tıklayabilir ya da (b) dikdörtgen veya poligon çizebilir (@mapbox/mapbox-gl-draw ya da terra-draw; MapLibre ile uyumlu olanı seç). Çizilen alan için en büyük su kütlesi analiz edilsin.
  - Altlık seçici: Vektör harita, NASA Blue Marble, günlük VIIRS (tarih seçici ile, GIBS).
  - Seçili gölde zaman kaydırıcısı: 1985 maskesi soluk mavi, seçilen yılın maskesi koyu mavi olarak bindirilsin. Oynat düğmesiyle animasyon olsun.
- [ ] Yan panel — göl detayı:
  - Canlı kartlar: alan, yüzey sıcaklığı, SWOT seviyesi, su yılı yağışı. Her kartta veri tarihi ve kaynak yazsın; önbellekten geliyorsa "önbellek" etiketi görünsün.
  - Alan grafiği: Sen doğrusu, güven bandı ve ortaya çıkış yılı dikey çizgisi.
  - Sıcaklık grafiği.
  - "İklim mi, insan mı?" grafiği: Gözlenen ve tahmin edilen kümülatif kayıp, aradaki fark gölgeli.
  - Hacim grafiği (varsa).
  - Özet cümle şablonla üretilsin, yapay zekâ ile değil. Örnek: "Burdur Gölü 1986'dan bu yana alanının %41'ini kaybetti (anlamlı, p<0,001). Kayıp 1998'de doğal dalgalanmadan ayrıştı. İklim değişkenleri kaybın yaklaşık %35'ini açıklıyor (GA %20–50)."
- [ ] İsteğe bağlı analiz akışı: Seçim yapılınca "Analiz et" düğmesi çıksın. Tıklanınca ilerleme çubuğu, işlenen yıl ve tahmini süre görünsün. Ön sonuç gelince grafikler çizilmeye başlasın.
- [ ] Karşılaştırma ekranı (/compare):
  - Seçilen en fazla 6 gölün normalleştirilmiş alan serileri tek grafikte (1985–1990 = %100).
  - Sıralama tablosu: %/on yıl kayıp, p, ortaya çıkış yılı, ısınma, iklimle açıklanan pay. Sütunlara göre sıralanabilsin; Türkiye gölleri vurgulansın.
  - Dağılım grafiği: x = ısınma hızı, y = alan trendi, nokta boyutu = göl alanı, renk = iklimle açıklanan pay. "Türkiye gölleri küresel dağılımın neresinde?" sorusunu görsel olarak cevaplasın.
  - Haritadan ya da listeden göl ekleyip çıkarmak mümkün olsun.
- [ ] Yöntem ve sınırlamalar sayfası (/methods): Veri kaynakları ve DOI'leri, yöntem, doğrulama sonuçları (VALIDATION.md'den), bilinen sınırlamalar.
- [ ] i18n: Türkçe ve İngilizce. Varsayılan İngilizce olsun, çünkü jüri uluslararası.
- [ ] Tasarım: Koyu harita teması. Renkler tutarlı olsun: su için mavi, sıcaklık için turuncu, iklim modeli için gri. Her grafikte eksen birimi ve veri kaynağı yazsın. Erişilebilirlik için renk körü dostu bir palet kullan ve renkleri etiketlerle destekle. 1280 px genişlikte sorunsuz görünsün; mobilde panel alttan açılsın.
- Kabul kriteri: Haritada Burdur'a tıklayınca 2 saniye içinde detay paneli açılıyor. Çizilen bir poligon analiz işi başlatıyor ve ilerleme görünüyor.
AŞAMA 6 — Küresel referans gölleri (Halka 2)
Önceden hesaplanacak referans göller. Farklı kayıp nedenlerini temsil etmeleri için seçildiler. Her biri için literatürdeki genel eğilimle (azalma ya da artış) yön karşılaştırması yap ve VALIDATION.md'ye yaz:
Göl Ülke Neden seçildi
Urmiye (Orumiye) İran Türkiye'ye komşu, hızlı küçülen tuzlu göl, sulama baskısı
Aral Denizi (Güney ve Kuzey) Kazakistan / Özbekistan Sulama kaynaklı çöküşün klasik örneği. Kuzey kısımda baraj sonrası kısmi toparlanma
Büyük Tuz Gölü (Great Salt Lake) ABD Kurak bölge, su kullanımı ve kuraklık
Mead Gölü ABD Baraj gölü, kuraklık ve tahsis
Çad Gölü Çad / Nijer / Nijerya / Kamerun Sahel iklim değişkenliği
Poopó Gölü Bolivya Sığ göl, tamamen kuruma olayları
Titikaka Gölü Peru / Bolivya Görece istikrarlı büyük göl, kontrol
Balkaş Gölü Kazakistan Kapalı havza, sulama baskısı
Sevan Gölü Ermenistan Bölgesel, tarihî su çekimi ve toparlanma
Tuz Gölü Türkiye Yalnızca bu aşamada, mevsimsellik uyarısıyla
Qinghai Gölü Çin Artan göl örneği (Tibet Platosu)
Ölü Deniz İsrail / Ürdün Hızlı seviye düşüşü
- Çok büyük göllerde (Aral, Çad, Balkaş) uyarlanabilir çözünürlüğü kullan.
- Çad ve Poopó gibi mevsimsel su bitkisi ya da sığlık sorunları olan göllerde MNDWI sınırlamasını göl sayfasında belirt.
- Hazar Denizi'ni ekleme. Çok büyük ve kutu sınırları pratik değil.
- Kabul kriteri: /api/lakes en az 10 referans gölü döndürüyor. Karşılaştırma ekranında Türkiye gölleri ile referans göller birlikte görünüyor.
AŞAMA 7 — Demo güvenilirliği (kritik)
- [ ] Çevrimdışı yedek: Her canlı çağrının son başarılı sonucu data/live_cache/ altında dursun. API erişilemezse buradan gösterilsin.
- [ ] scripts/prefetch.py: Tüm canlı veriyi ve GIBS görüntülerini tek komutla önceden çekip önbelleğe alsın. Sunumdan önce çalıştırılacak.
- [ ] Altlık için çevrimdışı yedek: GIBS ya da OpenFreeMap erişilemezse basit bir yerel ülke sınırları GeoJSON'u altlık olarak gösterilsin.
- [ ] İsteğe bağlı analiz için demo modu: Önceden hesaplanmış bir "örnek iş" (ör. Sevan) hazır olsun. Sunumda canlı iş beklemek yerine iş akışı bu kayıtla birkaç saniyede gösterilebilsin. Arayüzde bunu açıkça "önceden hesaplanmış örnek" olarak etiketle.
- Kabul kriteri: İnternet kapalıyken docker-compose up ile uygulama açılıyor; tüm önceden hesaplanmış göller, karşılaştırma ekranı ve önbellekteki canlı kartlar çalışıyor.
AŞAMA 8 — Test ve teslim materyalleri
- [ ] Backend testleri (pytest):
  - Sentetik göl: Alan ve sıcaklık (bilinen daire alanı, su 20 °C, kara 35 °C).
  - Landsat 5 + Landsat 8 birleştirme.
  - Otomatik UTM: Burdur → 32636, Van → 32638, Titikaka → 32719.
  - Ortaya çıkış yılı ve ayrıştırma (sentetik seriler).
  - Sahte yanıtlarla POWER ve Hydrocron ayrıştırma (no_data satırları dahil).
  - API sözleşme testleri (FastAPI TestClient).
  - İş kuyruğu: Aynı göl için tekrarlanan istekler tek işe bağlanıyor.
- [ ] Frontend: Temel bileşen testleri (Vitest) ve bir uçtan uca senaryo (Playwright): Haritayı aç → Burdur'a tıkla → panel açılsın → karşılaştırmaya ekle.
- [ ] README.md (İngilizce): Proje özeti, ekran görüntüleri ya da GIF, kurulum, çalıştırma, mimari şeması, veri kaynakları ve DOI'leri, yöntem, doğrulama, sınırlamalar, takım.
- [ ] docs/project_summary.md: Space Apps proje sayfası için İngilizce metin (problem, çözüm, NASA verisi, etki, yapay zekâ kullanımı beyanı).
- [ ] docs/demo_script.md: 30 saniyelik video ve 7 slaytlık sunum akışı. Önerilen hikâye: Burdur'un kaybı → "iklim mi, insan mı?" grafiği → haritada Urmiye ve Aral'a geçiş → karşılaştırma dağılım grafiğinde Türkiye'nin yeri → canlı kartlar ve haritada yeni bir gölün seçilmesi.
————
4. Teknik kurallar
- Python 3.11+ (tip ipuçları, kısa docstring'ler). TypeScript strict mode. API tipleri OpenAPI'den otomatik üretilsin (openapi-typescript).
- Gizli anahtar yok. Earthdata gerekiyorsa ~/.netrc ya da EARTHDATA_TOKEN ortam değişkeni kullan, koda gömme.
- Bir kaynağın hatası diğerlerini durdurmasın (mevcut _ok / _fail desenini koru).
- Ağ çağrılarında zaman aşımı, 2 deneme ve üstel bekleme kullan. Planetary Computer'a eşzamanlı istekleri sınırla.
- Landsat'ı yalnızca göl kutusu kadar bbox ile yükle. Dask chunk boyutlarını makul tut. Bir yılın hatası tüm seriyi durdurmasın; o yılı NaN ve hata notuyla geç.
- Önceden hesaplanan her çıktıya üretildiği tarih, kod sürümü, çözünürlük, UTM zonu ve kullanılan sahne sayıları içeren bir meta.json ekle.
- Frontend'de API yanıtları TanStack Query ile önbelleğe alınsın. Harita etkileşimi akıcı kalsın; ağır GeoJSON'lar basitleştirilsin (mapshaper ya da shapely.simplify).
- Her aşamadan sonra küçük ve anlamlı bir commit at.
5. Bilimsel dürüstlük kuralları (jüri için kritik)
- NASA POWER ve MERRA-2 model tabanlı veridir; istasyon ölçümü gibi sunma.
- SWOT kaydı (2023'ten beri) uzun dönem trend için kısa. Trendi Landsat'tan al.
- Landsat 5'ten 8'e geçişte (2012) sıcaklıkta kalibrasyon sıçraması olabilir. 2013 öncesi ile sonrasını ayrı ayrı da test et ve sonucu belirt.
- İsteğe bağlı analizlerin sonuçları doğrulanmamış olarak etiketlensin. Yalnızca Türkiye gölleri ve literatürle karşılaştırılmış referans göller "doğrulanmış" rozeti alsın.
- Küresel karşılaştırmada farklı büyüklükteki gölleri adil karşılaştırmak için mutlak km² değil, normalleştirilmiş yüzde kullan. Çözünürlük farklarını (30 m ve 120 m) karşılaştırma ekranında belirt.
- Anlamlılık için p < 0.05 kullan, p değerini ve güven aralığını her zaman göster.
- Hiçbir sayıyı uydurma. Bir hesap başarısız olursa arayüzde "veri yok" göster.
- Sonuç bir literatür değeriyle çelişiyorsa gizleme. VALIDATION.md'ye yaz ve olası sebebi açıkla.
- Sınır aşan göllerde (Aral, Çad, Ölü Deniz, Titikaka) tarafsız ve yalnızca veriye dayalı bir dil kullan.
6. Yapma
- Aşama 1 doğrulanmadan ve Türkiye gölleri uçtan uca çalışmadan küresel kısma geçme.
- Mapbox ya da token gerektiren başka bir harita servisi kullanma.
- Canlı Landsat hesabını sayfa her açıldığında tekrarlama (önbellek kullan).
- Özet cümleleri dil modeliyle üretme; şablon kullan ki sayılar her zaman veriyle tutarlı olsun.
- Kullanıcının çizdiği büyük poligonları sınırsız işleme (20.000 km² sınırı).
7. Her aşama sonunda bana şunu raporla
1. Ne yapıldı (dosyalar)
2. Kabul kriterinin sonucu (sayılarla)
3. Karşılaşılan sorunlar ve yaptığın varsayımlar
4. Kalan süreye göre bir sonraki adım önerisi (gerekiyorsa kapsam daraltma önerisiyle)
Belirsiz bir karar varsa (ör. eşik değeri, havza sınırı, kütüphane seçimi) en makul seçeneği uygula, gerekçesini rapora yaz ve devam et. Yalnızca geri alınamaz işlemlerde dur ve sor.;


Bu prompt'u uygulayarak çalış SpaceAPPS repositorysine kaydet
