"use client";

import * as React from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SearchableSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

export function SearchableSelect({
  value,
  onChange,
  options,
  disabled = false,
  placeholder = "Select language...",
  className,
}: SearchableSelectProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [searchQuery, setSearchQuery] = React.useState("");
  const containerRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const listRef = React.useRef<HTMLUListElement>(null);

  // Close when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearchQuery(""); // Reset search on close
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Focus input when opening
  React.useEffect(() => {
    if (isOpen) {
      // Small timeout to ensure render
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const selectedOption = options.find((opt) => opt.value === value);

  const filteredOptions = React.useMemo(() => {
    if (!searchQuery) return options;
    const lowerQuery = searchQuery.toLowerCase();
    return options.filter(
      (opt) =>
        opt.label.toLowerCase().includes(lowerQuery) ||
        opt.value.toLowerCase().includes(lowerQuery)
    );
  }, [options, searchQuery]);

  const handleSelect = (optionValue: string) => {
    onChange(optionValue);
    setIsOpen(false);
    setSearchQuery("");
  };

  return (
    <div ref={containerRef} className={cn("relative w-full", className)}>
      {/* Trigger Button */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className={cn(
          "relative w-full appearance-none px-3 py-2 pr-10 text-left text-sm font-medium",
          "rounded-lg border border-gray-200 dark:border-gray-600",
          "bg-white dark:bg-gray-900",
          "text-gray-900 dark:text-gray-100",
          "transition-all cursor-pointer hover:border-gray-300 dark:hover:border-gray-500",
          "focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500",
          disabled && "opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800"
        )}
      >
        <span className={cn("block truncate", !selectedOption && "text-gray-500")}>
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400">
          <ChevronDown
            className={cn("h-4 w-4 transition-transform duration-200", isOpen && "rotate-180")}
          />
        </span>
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute z-50 mt-1 w-full rounded-lg bg-white dark:bg-gray-800 shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden animate-in fade-in zoom-in-95 duration-100">
          {/* Search Input */}
          <div className="flex items-center border-b border-gray-100 dark:border-gray-700 px-3 py-2">
            <Search className="h-4 w-4 text-gray-400 mr-2 shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search languages..."
              className="w-full bg-transparent border-none p-0 text-sm focus:ring-0 placeholder:text-gray-400 text-gray-900 dark:text-gray-100"
              onKeyDown={(e) => {
                if (e.key === "Enter" && filteredOptions.length > 0) {
                  handleSelect(filteredOptions[0].value);
                }
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="ml-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>

          {/* Options List */}
          <ul
            ref={listRef}
            className="max-h-60 overflow-auto py-1 text-sm scrollbar-thin scrollbar-thumb-gray-200 dark:scrollbar-thumb-gray-700"
          >
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option) => {
                const isSelected = option.value === value;
                return (
                  <li
                    key={option.value}
                    onClick={() => handleSelect(option.value)}
                    className={cn(
                      "relative cursor-pointer select-none py-2 pl-3 pr-9",
                      "text-gray-900 dark:text-gray-100",
                      "hover:bg-gray-100 dark:hover:bg-gray-700/50",
                      isSelected && "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 font-medium"
                    )}
                  >
                    <span className="block truncate">{option.label}</span>
                    {isSelected && (
                      <span className="absolute inset-y-0 right-0 flex items-center pr-3 text-emerald-600 dark:text-emerald-400">
                        <Check className="h-4 w-4" />
                      </span>
                    )}
                  </li>
                );
              })
            ) : (
              <li className="py-4 text-center text-gray-500 text-xs italic">
                No languages found
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
