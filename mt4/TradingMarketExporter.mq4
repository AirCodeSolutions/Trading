#property strict

input string SymbolsCsv = "EURUSD,GBPUSD,XAUUSD,XAGUSD,BTCUSD,US500Cash";
input int ExportEverySeconds = 5;

string symbols[];

int OnInit()
{
   StringSplit(SymbolsCsv, ',', symbols);
   EventSetTimer(MathMax(1, ExportEverySeconds));
   ExportSnapshot();
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   ExportSnapshot();
}

void ExportSnapshot()
{
   int handle = FileOpen(
      "trading_symbol_specs.csv",
      FILE_WRITE|FILE_CSV|FILE_ANSI,
      ','
   );
   if(handle == INVALID_HANDLE)
      return;

   FileWrite(
      handle,
      "timestamp","symbol","bid","ask","digits","contract_size",
      "tick_size","tick_value","point","min_lot","max_lot","lot_step",
      "stop_level","margin_required"
   );

   for(int i = 0; i < ArraySize(symbols); i++)
   {
      string symbol = symbols[i];
      StringTrimLeft(symbol);
      StringTrimRight(symbol);
      if(symbol == "")
         continue;

      SymbolSelect(symbol, true);
      FileWrite(
         handle,
         TimeCurrent(),
         symbol,
         MarketInfo(symbol, MODE_BID),
         MarketInfo(symbol, MODE_ASK),
         (int)MarketInfo(symbol, MODE_DIGITS),
         MarketInfo(symbol, MODE_LOTSIZE),
         MarketInfo(symbol, MODE_TICKSIZE),
         MarketInfo(symbol, MODE_TICKVALUE),
         MarketInfo(symbol, MODE_POINT),
         MarketInfo(symbol, MODE_MINLOT),
         MarketInfo(symbol, MODE_MAXLOT),
         MarketInfo(symbol, MODE_LOTSTEP),
         MarketInfo(symbol, MODE_STOPLEVEL),
         MarketInfo(symbol, MODE_MARGINREQUIRED)
      );
   }

   FileClose(handle);
}
