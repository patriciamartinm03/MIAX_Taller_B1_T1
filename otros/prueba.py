import yfinance as yf

apple = yf.Ticker("AAPL")
datos = apple.history(period="1y")

print(datos.head())
print(datos["Close"].mean())
