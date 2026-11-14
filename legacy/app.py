"""
Göl Kaybı Dedektörü — arayüz.   Çalıştırma:  pip install streamlit  &&  streamlit run app.py

Üst bölüm: CANLI durum (NASA API'lerinden, 3 saatte bir yenilenir).
Alt bölüm: 40 yıllık geçmiş (burdur_area.py çıktısı <göl>_area.csv dosyasından).
"""
import os

import pandas as pd
import streamlit as st

from live_data import LAKES, gibs_image_url, landsat_now, precip_now, swot_now

st.set_page_config(page_title="Göl Kaybı Dedektörü", page_icon="💧", layout="wide")
TTL = 3 * 3600

@st.cache_data(ttl=TTL, show_spinner="NASA POWER sorgulanıyor…")
def c_precip(k): return precip_now(LAKES[k])

@st.cache_data(ttl=TTL, show_spinner="SWOT (Hydrocron) sorgulanıyor…")
def c_swot(k): return swot_now(LAKES[k])

@st.cache_data(ttl=TTL, show_spinner="Son Landsat sahneleri işleniyor (1–2 dk)…")
def c_landsat(k): return landsat_now(LAKES[k])


key = st.sidebar.selectbox("Göl", list(LAKES), format_func=lambda k: LAKES[k]["name"])
lake = LAKES[key]
run_landsat = st.sidebar.checkbox("Canlı Landsat alanını hesapla", value=True)
if st.sidebar.button("Önbelleği temizle ve yenile"):
    st.cache_data.clear()

st.title(f"💧 {lake['name']} Gölü — Kayıp Dedektörü")
st.caption("Göllerimiz küçülüyor. Ama ne kadarı iklim, ne kadarı biz?  ·  NASA Space Apps 2026")

# ------------------------------------------------------------------ CANLI
st.subheader("🔴 Şu an")
c1, c4, c2, c3 = st.columns(4)

L = c_landsat(key) if run_landsat else None
with c1:
    if L is None:
        st.info("Canlı Landsat kapalı")
    elif L["ok"]:
        st.metric("Göl alanı (son 45 gün)", f"{L['area_km2']} km²",
                  f"{L['change_vs_last_year_pct']:+} % geçen yıla göre" if L["change_vs_last_year_pct"] is not None else None)
        st.caption(f"Landsat · son sahne {L['latest_scene']} · kapsama {L['valid_frac']:.0%}")
    else:
        st.warning(f"Landsat: {L['error']}")

with c4:
    if L is not None and L["ok"] and L.get("lst_c") == L.get("lst_c") and L.get("lst_c") is not None:
        d = L.get("lst_change_vs_last_year_c")
        st.metric("Göl yüzey sıcaklığı (son 45 gün)", f"{L['lst_c']:.1f} °C",
                  f"{d:+.1f} °C geçen yıla göre" if d is not None else None, delta_color="inverse")
        st.caption(f"Landsat termal · {L['lst_px']} saf su pikseli (kıyıdan ≥150 m)")
    elif L is not None and L["ok"]:
        st.info("Sıcaklık için yeterli bulutsuz saf su pikseli yok")

with c2:
    S = c_swot(key)
    if S["ok"]:
        st.metric("Su seviyesi (SWOT)", f"{S['wse_m']} m",
                  f"{S['wse_change_1y_m']:+} m / 1 yıl" if S["wse_change_1y_m"] is not None else None)
        st.caption(f"SWOT · son geçiş {S['last_obs']} · {S['n_obs']} ölçüm")
        ser = pd.DataFrame(S["series"], columns=["tarih", "seviye_m"]).set_index("tarih")
        st.line_chart(ser, height=120)
    else:
        st.warning(f"SWOT: {S['error']}")

with c3:
    P = c_precip(key)
    if P["ok"]:
        st.metric("Su yılı yağışı (havza)", f"{P['precip_mm']} mm",
                  f"normalin %{P['pct_of_normal']}'i" if P["pct_of_normal"] else None,
                  delta_color="normal" if (P["pct_of_normal"] or 100) >= 100 else "inverse")
        st.caption(f"NASA POWER · {P['water_year_start']} → {P['data_until']} · normal {P['normal_mm']} mm (1991–2020)")
    else:
        st.warning(f"POWER: {P['error']}")

st.image(gibs_image_url(lake), caption="Dünkü uydu görüntüsü — NASA GIBS, VIIRS NOAA-20 gerçek renk",
         use_container_width=True)

# ------------------------------------------------------------------ GEÇMİŞ
st.subheader("📉 40 yıllık kayıt")
csv = f"{lake['name'].lower().replace('ş','s').replace('ğ','g')}_area.csv"
if os.path.exists(csv):
    df = pd.read_csv(csv)
    good = df[df.valid_frac >= 0.8].dropna(subset=["area_km2"])
    st.line_chart(good.set_index("year")["area_km2"], height=300)
    if len(good) >= 10:
        import pymannkendall as mk
        r = mk.hamed_rao_modification_test(good.area_km2.values)
        a, b = good.iloc[0], good.iloc[-1]
        k1, k2, k3 = st.columns(3)
        k1.metric(f"{int(a.year)} → {int(b.year)}", f"{b.area_km2:.0f} km²",
                  f"{100*(b.area_km2-a.area_km2)/a.area_km2:+.0f} %")
        k2.metric("Trend (Sen eğimi)", f"{r.slope*10:+.1f} km²/on yıl")
        k3.metric("Anlamlı mı?", "Evet" if r.p < 0.05 else "Hayır", f"p = {r.p:.3g}", delta_color="off")

    if "lst_c" in good and good.lst_c.notna().sum() >= 10:
        st.subheader("🌡️ Göl yüzey sıcaklığı (yaz sonu)")
        t = good.dropna(subset=["lst_c"])
        st.line_chart(t.set_index("year")["lst_c"], height=250, color="#d35400")
        rt = mk.hamed_rao_modification_test(t.lst_c.values)
        s1, s2 = st.columns(2)
        s1.metric("Isınma hızı (Sen eğimi)", f"{rt.slope*10:+.2f} °C/on yıl")
        s2.metric("Anlamlı mı?", "Evet" if rt.p < 0.05 else "Hayır", f"p = {rt.p:.3g}", delta_color="off")
        st.caption("Karşılaştırma için: dünya göllerinin yaz yüzey sıcaklığı 1985–2009 arasında ortalama "
                   "yaklaşık 0,34 °C/on yıl ısındı (O'Reilly ve ark., 2015). Isınan göl daha çok buharlaşır.")
else:
    st.info(f"`{csv}` bulunamadı. Önce `python burdur_area.py --name {lake['name']}` çalıştırın.")

with st.expander("Sınırlamalar ve veri kaynakları"):
    st.markdown("""
- **Landsat** yaz sonu (Ağu–Eyl) kompozitleri; bulut ve gölge maskelenir. Canlı alan mevsime bağlıdır, geçmişle değil geçen yılın aynı dönemiyle karşılaştırılır.
- **SWOT** 2023'ten beri ölçüyor: uzun dönem trend için kısa, güncel seviye için çok değerli.
- **NASA POWER** model tabanlı (MERRA-2/GEOS) yağıştır, istasyon ölçümü değildir; havzadaki birkaç noktanın ortalaması alınır.
- **Göl yüzey sıcaklığı** Landsat termal bandından (Collection 2 Level-2 ST) alınır: suyun en üst milimetresinin "deri" sıcaklığıdır, derin su sıcaklığı değildir. Kıyı karışımını önlemek için yalnızca kıyıdan ≥150 m uzaktaki su pikselleri kullanılır. Landsat 5 ile 8/9 termal sensörleri arasında ~0,5–1 °C'lik kalibrasyon farkı olabilir; 2012 geçişindeki sıçramaya dikkat edin.
- "İklimle açıklanamayan kayıp" insan etkisinin **kanıtı değil, işaretidir**.
""")
