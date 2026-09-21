#property strict

input string SymbolsCsv = "BTCUSD,EURUSD,GBPUSD,XAUUSD,XAGUSD";
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

   long timestamp = (long)TimeCurrent();

   for(int i = 0; i < ArraySize(symbols); i++)
   {
      string symbol = symbols[i];
      StringTrimLeft(symbol);
      StringTrimRight(symbol);
      if(symbol == "")
         continue;

      if(!SymbolSelect(symbol, true))
         continue;

      double bid = MarketInfo(symbol, MODE_BID);
      double ask = MarketInfo(symbol, MODE_ASK);
      double tickSize = MarketInfo(symbol, MODE_TICKSIZE);
      double tickValue = MarketInfo(symbol, MODE_TICKVALUE);
      double minLot = MarketInfo(symbol, MODE_MINLOT);
      double lotStep = MarketInfo(symbol, MODE_LOTSTEP);

      // Skip aliases or unavailable instruments instead of exporting zero quotes.
      if(
         bid <= 0
         || ask <= 0
         || ask < bid
         || tickSize <= 0
         || tickValue <= 0
         || minLot <= 0
         || lotStep <= 0
      )
         continue;

      FileWrite(
         handle,
         timestamp,
         symbol,
         bid,
         ask,
         (int)MarketInfo(symbol, MODE_DIGITS),
         MarketInfo(symbol, MODE_LOTSIZE),
         tickSize,
         tickValue,
         MarketInfo(symbol, MODE_POINT),
         minLot,
         MarketInfo(symbol, MODE_MAXLOT),
         lotStep,
         MarketInfo(symbol, MODE_STOPLEVEL),
         MarketInfo(symbol, MODE_MARGINREQUIRED)
      );
   }

   FileFlush(handle);
   FileClose(handle);
}
