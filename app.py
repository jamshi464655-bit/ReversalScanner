import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
from concurrent.futures import ThreadPoolExecutor

# Page Configuration
st.set_page_config(page_title="SwingPro Reversal", layout="wide")

URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsnZ6oD_zaP3JLOVaAbR1ZTzn2TVQ26agPr_G89Iey669ijjuJnwgbiaJDtdBiF1ixVyZ0gtfTA1e8/pub?output=csv"

def analyze_reversal(symbol):
    try:
        ticker = f"{symbol}.NS"
        # 6 മാസത്തെ ഡാറ്റ എടുക്കുന്നു. group_by="column" നൽകുന്നത് Multi-index ഒഴിവാക്കാൻ സഹായിക്കും
        df = yf.download(ticker, period="6mo", interval="1d", progress=False, group_by="column")
        if df.empty or len(df) < 30: 
            return None

        # yfinance പുതിയ അപ്ഡേറ്റുകളിലെ Multi-index കോളം പ്രശ്നം പരിഹരിക്കാൻ
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        # വിലകൾ ഫ്ലോട്ട് (Float) വാല്യൂസ് ആയി മാറ്റുന്നു
        close_series = df['Close'].astype(float)

        ltp = close_series.iloc[-1]
        rsi_series = ta.rsi(close_series, length=14)
        ema_series = ta.ema(close_series, length=20)

        if rsi_series is None or ema_series is None or rsi_series.empty or ema_series.empty:
            return None

        rsi = rsi_series.iloc[-1]
        ema_20 = ema_series.iloc[-1]
        
        # EMA 20-ൽ നിന്നും വില എത്ര ശതമാനം താഴെയാണെന്ന് നോക്കുന്നു
        distance_from_ema = ((ltp - ema_20) / ema_20) * 100

        status = "⚪ Neutral"
        
        # ലോജിക്: RSI 35-ൽ താഴെ (Oversold) + EMA 20-ൽ നിന്നും 5% എങ്കിലും താഴെ
        if rsi < 35 and distance_from_ema < -5:
            status = "🔥 BOTTOM FISHING (BUY)"
        elif rsi > 75:
            status = "⚠️ OVERBOUGHT (SELL/BOOK PROFIT)"

        return {
            "Stock": symbol,
            "LTP": round(float(ltp), 2),
            "RSI": round(float(rsi), 2),
            "Gap from EMA%": round(float(distance_from_ema), 2),
            "Signal": status
        }
    except Exception:
        return None

# UI Design
st.markdown("<h1 style='text-align: center; color: #E91E63;'>Reversal & Bottom Fishing 🎣</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 18px;'>വല്ലാതെ താഴേക്ക് പോയ സ്റ്റോക്കുകളുടെ തിരിച്ചുവരവ് (Mean Reversion) ഈ സ്കാനർ കണ്ടെത്തും.</p>", unsafe_allow_html=True)

if st.button('🔍 സ്കാനിംഗ് തുടങ്ങുക', use_container_width=True):
    try:
        with st.spinner("ഗൂഗിൾ ഷീറ്റിൽ നിന്നും സ്റ്റോക്കുകൾ ശേഖരിക്കുന്നു..."):
            sheet_df = pd.read_csv(URL)
            # ഫോർമാറ്റ് കൃത്യമാക്കാൻ കോളം പേരുകളിലെ സ്പേസ് ഒഴിവാക്കുന്നു
            sheet_df.columns = sheet_df.columns.str.strip()
            symbols = sheet_df['Symbol'].dropna().unique().tolist()
            
        if not symbols:
            st.error("ഗൂഗിൾ ഷീറ്റിൽ നിന്നും സ്റ്റോക്കുകൾ കണ്ടെത്താൻ കഴിഞ്ഞില്ല!")
        else:
            # ആദ്യത്തെ 100 സ്റ്റോക്കുകൾ മാത്രം എടുക്കുന്നു
            target_symbols = symbols[:100]
            total_stocks = len(target_symbols)
            
            results = []
            st.info(f"ആകെ {total_stocks} സ്റ്റോക്കുകൾ വേഗത്തിൽ സ്കാൻ ചെയ്യുന്നു. ദയവായി കാത്തിരിക്കുക...")
            
            # ThreadPoolExecutor ഉപയോഗിച്ച് സ്കാനിംഗ് സ്പീഡ് വർദ്ധിപ്പിക്കുന്നു
            with ThreadPoolExecutor(max_workers=20) as executor:
                res_list = list(executor.map(analyze_reversal, target_symbols))
                results = [r for r in res_list if r]

            if results:
                final_df = pd.DataFrame(results)
                # ⚪ Neutral അല്ലാത്ത സിഗ്നലുകൾ മാത്രം ഫിൽട്ടർ ചെയ്യുന്നു
                signals_df = final_df[final_df['Signal'] != "⚪ Neutral"]
                
                if not signals_df.empty:
                    st.subheader("🎯 തിരിച്ചുകയറാൻ സാധ്യതയുള്ള സ്റ്റോക്കുകൾ")
                    # ഭംഗിയുള്ള ഡിസ്‌പ്ലേയ്ക്ക് വേണ്ടി st.dataframe ഉപയോഗിക്കാം
                    st.dataframe(
                        signals_df.sort_values(by="RSI", ascending=True), 
                        use_container_width=True, 
                        hide_index=True
                    )
                else:
                    st.warning("നിലവിൽ പവർഫുൾ റിവേഴ്സൽ സിഗ്നലുകൾ (Oversold/Overbought) ഉള്ള സ്റ്റോക്കുകൾ ഒന്നുമില്ല.")
            else:
                st.error("മാർക്കറ്റ് ഡാറ്റ വിശകലനം ചെയ്യാൻ സാധിച്ചില്ല.")
                
    except Exception as e:
        st.error(f"പ്രവർത്തനത്തിൽ തടസ്സം നേരിട്ടു: {e}")