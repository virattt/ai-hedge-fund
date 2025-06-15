// app/next-frontend/components/portfolio/backtest-setup.tsx
"use client";

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { Checkbox } from '@/components/ui/checkbox';
import { CalendarIcon } from 'lucide-react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

export default function BacktestSetup() {
  const [startDate, setStartDate] = useState<Date | undefined>(new Date(new Date().setFullYear(new Date().getFullYear() - 1)));
  const [endDate, setEndDate] = useState<Date | undefined>(new Date());
  const [initialInvestment, setInitialInvestment] = useState('10000');
  const [rebalancing, setRebalancing] = useState('none');

  const handleRunBacktest = () => {
    // Placeholder for actual backtest logic
    alert(`Running backtest from ${startDate ? format(startDate, 'PPP') : ''} to ${endDate ? format(endDate, 'PPP') : ''} with $${initialInvestment} and ${rebalancing} rebalancing.`);
  };

  return (
    <div className="space-y-6 p-6 border rounded-lg">
      <h3 className="text-xl font-semibold">Configure Backtest</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <Label htmlFor="startDate">Start Date</Label>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant={"outline"}
                className={cn("w-full justify-start text-left font-normal", !startDate && "text-muted-foreground")}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {startDate ? format(startDate, "PPP") : <span>Pick a date</span>}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar mode="single" selected={startDate} onSelect={setStartDate} initialFocus />
            </PopoverContent>
          </Popover>
        </div>
        <div>
          <Label htmlFor="endDate">End Date</Label>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant={"outline"}
                className={cn("w-full justify-start text-left font-normal", !endDate && "text-muted-foreground")}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {endDate ? format(endDate, "PPP") : <span>Pick a date</span>}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar mode="single" selected={endDate} onSelect={setEndDate} initialFocus />
            </PopoverContent>
          </Popover>
        </div>
        <div>
          <Label htmlFor="initialInvestment">Initial Investment ($)</Label>
          <Input
            id="initialInvestment"
            type="number"
            value={initialInvestment}
            onChange={(e) => setInitialInvestment(e.target.value)}
            placeholder="e.g., 10000"
          />
        </div>
        <div>
          <Label htmlFor="rebalancing">Rebalancing Frequency</Label>
          <Select value={rebalancing} onValueChange={setRebalancing}>
            <SelectTrigger id="rebalancing">
              <SelectValue placeholder="Select frequency" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">None</SelectItem>
              <SelectItem value="monthly">Monthly</SelectItem>
              <SelectItem value="quarterly">Quarterly</SelectItem>
              <SelectItem value="annual">Annual</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex items-center space-x-2 mt-4">
         {/* <Checkbox id="terms" /> <Label htmlFor="terms">I acknowledge this is a simulation.</Label> */}
      </div>
      <Button onClick={handleRunBacktest} className="w-full md:w-auto">Run Backtest</Button>
    </div>
  );
}
