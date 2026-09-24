#property strict

input bool AllowDemoExecution = true;
input int MagicNumber = 560619;
input int PollEverySeconds = 1;

string COMMAND_FILE = "trading_demo_command.csv";
string CLOSE_COMMAND_FILE = "trading_demo_close_command.csv";
string RESULT_FILE = "trading_demo_result.csv";
string POSITIONS_FILE = "trading_demo_positions.csv";
string EXECUTION_LOCK_FILE = "trading_demo_execution.lock";

int OnInit()
{
   EventSetTimer(MathMax(1, PollEverySeconds));
   ExportSymbolSnapshot();
   ExportPositions();
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   ExportSymbolSnapshot();
   ProcessCloseCommand();
   ProcessCommand();
   ExportPositions();
}

string SymbolSnapshotFile()
{
   return "trading_demo_spec_" + Symbol() + ".csv";
}

void ExportSymbolSnapshot()
{
   string symbol = Symbol();
   double bid = MarketInfo(symbol, MODE_BID);
   double ask = MarketInfo(symbol, MODE_ASK);
   double tickSize = MarketInfo(symbol, MODE_TICKSIZE);
   double tickValue = MarketInfo(symbol, MODE_TICKVALUE);
   double minLot = MarketInfo(symbol, MODE_MINLOT);
   double maxLot = MarketInfo(symbol, MODE_MAXLOT);
   double lotStep = MarketInfo(symbol, MODE_LOTSTEP);

   if(
      bid <= 0
      || ask <= 0
      || ask < bid
      || tickSize <= 0
      || tickValue <= 0
      || minLot <= 0
      || maxLot <= 0
      || lotStep <= 0
   )
      return;

   int handle = FileOpen(
      SymbolSnapshotFile(),
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
   FileWrite(
      handle,
      (long)TimeCurrent(),
      symbol,
      bid,
      ask,
      (int)MarketInfo(symbol, MODE_DIGITS),
      MarketInfo(symbol, MODE_LOTSIZE),
      tickSize,
      tickValue,
      MarketInfo(symbol, MODE_POINT),
      minLot,
      maxLot,
      lotStep,
      MarketInfo(symbol, MODE_STOPLEVEL),
      MarketInfo(symbol, MODE_MARGINREQUIRED)
   );
   FileFlush(handle);
   FileClose(handle);
}

int AcquireExecutionLock()
{
   return FileOpen(
      EXECUTION_LOCK_FILE,
      FILE_READ|FILE_WRITE|FILE_BIN
   );
}

void ProcessCloseCommand()
{
   if(!FileIsExist(CLOSE_COMMAND_FILE))
      return;

   int lockHandle = AcquireExecutionLock();
   if(lockHandle == INVALID_HANDLE)
      return;

   ProcessCloseCommandLocked();
   FileClose(lockHandle);
}

void ProcessCloseCommandLocked()
{
   if(!FileIsExist(CLOSE_COMMAND_FILE))
      return;

   int handle = FileOpen(CLOSE_COMMAND_FILE, FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
      return;

   string commandId = FileReadString(handle);
   int ticket = (int)FileReadNumber(handle);
   string symbol = FileReadString(handle);
   string strategyId = FileReadString(handle);
   string issuedAt = FileReadString(handle);
   int commandMagic = (int)FileReadNumber(handle);
   int slippagePoints = (int)FileReadNumber(handle);
   FileClose(handle);

   if(commandId == "")
   {
      FileDelete(CLOSE_COMMAND_FILE);
      return;
   }

   if(symbol != Symbol())
      return;

   if(!AllowDemoExecution)
   {
      WriteResult(commandId, "REFUSED", ticket, 9201, 0, 0, 0);
      FileDelete(CLOSE_COMMAND_FILE);
      return;
   }

   if(AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      WriteResult(commandId, "REFUSED", ticket, 9202, 0, 0, 0);
      FileDelete(CLOSE_COMMAND_FILE);
      return;
   }

   if(commandMagic != MagicNumber)
   {
      WriteResult(commandId, "REFUSED", ticket, 9203, 0, 0, 0);
      FileDelete(CLOSE_COMMAND_FILE);
      return;
   }

   if(!OrderSelect(ticket, SELECT_BY_TICKET))
   {
      WriteResult(commandId, "REFUSED", ticket, 9204, 0, 0, 0);
      FileDelete(CLOSE_COMMAND_FILE);
      return;
   }

   if(OrderMagicNumber() != MagicNumber)
   {
      WriteResult(commandId, "REFUSED", ticket, 9205, 0, 0, 0);
      FileDelete(CLOSE_COMMAND_FILE);
      return;
   }

   if(OrderSymbol() != Symbol())
   {
      WriteResult(commandId, "REFUSED", ticket, 9207, 0, 0, 0);
      FileDelete(CLOSE_COMMAND_FILE);
      return;
   }

   if(OrderCloseTime() > 0)
   {
      WriteResult(commandId, "FILLED", ticket, 0, OrderClosePrice(), 0, 0);
      FileDelete(CLOSE_COMMAND_FILE);
      return;
   }

   int orderType = OrderType();
   if(orderType != OP_BUY && orderType != OP_SELL)
   {
      WriteResult(commandId, "REFUSED", ticket, 9206, 0, 0, 0);
      FileDelete(CLOSE_COMMAND_FILE);
      return;
   }

   string orderSymbol = OrderSymbol();
   int digits = (int)MarketInfo(orderSymbol, MODE_DIGITS);
   RefreshRates();
   double closePrice = orderType == OP_BUY
      ? MarketInfo(orderSymbol, MODE_BID)
      : MarketInfo(orderSymbol, MODE_ASK);
   closePrice = NormalizeDouble(closePrice, digits);

   ResetLastError();
   bool closed = OrderClose(
      ticket,
      OrderLots(),
      closePrice,
      MathMax(0, slippagePoints),
      clrNONE
   );
   if(!closed)
   {
      int errorCode = GetLastError();
      WriteResult(commandId, "ERROR", ticket, errorCode, 0, 0, 0);
      FileDelete(CLOSE_COMMAND_FILE);
      return;
   }

   WriteResult(commandId, "FILLED", ticket, 0, closePrice, 0, 0);
   FileDelete(CLOSE_COMMAND_FILE);
}

void ProcessCommand()
{
   if(!FileIsExist(COMMAND_FILE))
      return;

   int lockHandle = AcquireExecutionLock();
   if(lockHandle == INVALID_HANDLE)
      return;

   ProcessCommandLocked();
   FileClose(lockHandle);
}

void ProcessCommandLocked()
{
   if(!FileIsExist(COMMAND_FILE))
      return;

   int handle = FileOpen(COMMAND_FILE, FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
      return;

   string commandId = FileReadString(handle);
   string symbol = FileReadString(handle);
   string side = FileReadString(handle);
   double lots = FileReadNumber(handle);
   double stopLoss = FileReadNumber(handle);
   double takeProfit = FileReadNumber(handle);
   string strategyId = FileReadString(handle);
   string issuedAt = FileReadString(handle);
   int commandMagic = (int)FileReadNumber(handle);
   int slippagePoints = (int)FileReadNumber(handle);
   string proposalStatus = FileReadString(handle);
   FileClose(handle);

   if(commandId == "")
   {
      FileDelete(COMMAND_FILE);
      return;
   }

   if(symbol != Symbol())
      return;

   if(!AllowDemoExecution)
   {
      WriteResult(commandId, "REFUSED", 0, 9101, 0, stopLoss, takeProfit);
      FileDelete(COMMAND_FILE);
      return;
   }

   if(AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      WriteResult(commandId, "REFUSED", 0, 9102, 0, stopLoss, takeProfit);
      FileDelete(COMMAND_FILE);
      return;
   }

   if(commandMagic != MagicNumber)
   {
      WriteResult(commandId, "REFUSED", 0, 9103, 0, stopLoss, takeProfit);
      FileDelete(COMMAND_FILE);
      return;
   }

   if(proposalStatus != "authorized")
   {
      WriteResult(commandId, "REFUSED", 0, 9104, 0, stopLoss, takeProfit);
      FileDelete(COMMAND_FILE);
      return;
   }

   if(HasBridgePositionForSymbol(symbol))
   {
      WriteResult(commandId, "REFUSED", 0, 9105, 0, stopLoss, takeProfit);
      FileDelete(COMMAND_FILE);
      return;
   }

   if(!SymbolSelect(symbol, true))
   {
      WriteResult(commandId, "REFUSED", 0, 9106, 0, stopLoss, takeProfit);
      FileDelete(COMMAND_FILE);
      return;
   }

   RefreshRates();

   double minLot = MarketInfo(symbol, MODE_MINLOT);
   double maxLot = MarketInfo(symbol, MODE_MAXLOT);
   double lotStep = MarketInfo(symbol, MODE_LOTSTEP);
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);

   if(lotStep <= 0)
      lotStep = minLot;

   double normalizedLots = MathFloor(lots / lotStep + 1e-9) * lotStep;
   normalizedLots = NormalizeDouble(normalizedLots, 2);

   if(
      normalizedLots < minLot
      || normalizedLots > maxLot
      || MathAbs(normalizedLots - lots) > lotStep / 2.0
   )
   {
      WriteResult(commandId, "REFUSED", 0, 9107, 0, stopLoss, takeProfit);
      FileDelete(COMMAND_FILE);
      return;
   }

   int cmd = -1;
   double price = 0;
   if(side == "BUY")
   {
      cmd = OP_BUY;
      price = MarketInfo(symbol, MODE_ASK);
      if(!(stopLoss < price && takeProfit > price))
      {
         WriteResult(commandId, "REFUSED", 0, 9108, 0, stopLoss, takeProfit);
         FileDelete(COMMAND_FILE);
         return;
      }
   }
   else if(side == "SELL")
   {
      cmd = OP_SELL;
      price = MarketInfo(symbol, MODE_BID);
      if(!(takeProfit < price && stopLoss > price))
      {
         WriteResult(commandId, "REFUSED", 0, 9109, 0, stopLoss, takeProfit);
         FileDelete(COMMAND_FILE);
         return;
      }
   }
   else
   {
      WriteResult(commandId, "REFUSED", 0, 9110, 0, stopLoss, takeProfit);
      FileDelete(COMMAND_FILE);
      return;
   }

   price = NormalizeDouble(price, digits);
   stopLoss = NormalizeDouble(stopLoss, digits);
   takeProfit = NormalizeDouble(takeProfit, digits);

   ResetLastError();
   int ticket = OrderSend(
      symbol,
      cmd,
      normalizedLots,
      price,
      MathMax(0, slippagePoints),
      stopLoss,
      takeProfit,
      "TradingNew:" + strategyId,
      MagicNumber,
      0,
      clrNONE
   );

   if(ticket < 0)
   {
      int errorCode = GetLastError();
      WriteResult(commandId, "ERROR", 0, errorCode, 0, stopLoss, takeProfit);
      FileDelete(COMMAND_FILE);
      return;
   }

   double fillPrice = price;
   if(OrderSelect(ticket, SELECT_BY_TICKET))
      fillPrice = OrderOpenPrice();

   WriteResult(
      commandId,
      "FILLED",
      ticket,
      0,
      fillPrice,
      stopLoss,
      takeProfit
   );
   FileDelete(COMMAND_FILE);
}

bool HasBridgePositionForSymbol(string symbol)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderMagicNumber() != MagicNumber)
         continue;
      if(
         OrderSymbol() == symbol
         && (OrderType() == OP_BUY || OrderType() == OP_SELL)
      )
         return(true);
   }
   return(false);
}

void WriteResult(
   string commandId,
   string status,
   int ticket,
   int errorCode,
   double fillPrice,
   double stopLoss,
   double takeProfit
)
{
   int handle = FileOpen(
      RESULT_FILE,
      FILE_WRITE|FILE_CSV|FILE_ANSI,
      ','
   );
   if(handle == INVALID_HANDLE)
      return;

   FileWrite(
      handle,
      commandId,
      status,
      ticket,
      errorCode,
      DoubleToString(fillPrice, 8),
      DoubleToString(stopLoss, 8),
      DoubleToString(takeProfit, 8),
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS)
   );
   FileClose(handle);
}

void ExportPositions()
{
   int handle = FileOpen(
      POSITIONS_FILE,
      FILE_WRITE|FILE_CSV|FILE_ANSI,
      ','
   );
   if(handle == INVALID_HANDLE)
      return;

   FileWrite(
      handle,
      "ticket","symbol","side","lots","open_price",
      "stop_loss","take_profit","profit","open_time","comment"
   );

   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderMagicNumber() != MagicNumber)
         continue;
      if(OrderType() != OP_BUY && OrderType() != OP_SELL)
         continue;

      FileWrite(
         handle,
         OrderTicket(),
         OrderSymbol(),
         OrderType() == OP_BUY ? "BUY" : "SELL",
         DoubleToString(OrderLots(), 8),
         DoubleToString(OrderOpenPrice(), 8),
         DoubleToString(OrderStopLoss(), 8),
         DoubleToString(OrderTakeProfit(), 8),
         DoubleToString(
            OrderProfit() + OrderSwap() + OrderCommission(),
            8
         ),
         TimeToString(OrderOpenTime(), TIME_DATE|TIME_SECONDS),
         OrderComment()
      );
   }

   FileClose(handle);
}
