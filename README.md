# Pharmacy Management System

A command-line Pharmacy Management System built in Python for managing medicine inventory, restocking, pricing, sales billing, stock alerts, and CSV data import/export.

## Features

Based on the interactive menu in `main.py`, the application supports:

1. **Add Medicine** (`add_medicine`) – Register new medicines into the inventory[cite: 1].
2. **View Medicines** (`view_medicines`) – Display all available medicines and stock details[cite: 1].
3. **Search Medicine** (`search_medicine`) – Look up specific medicines quickly[cite: 1].
4. **Restock Medicine** (`restock_medicine`) – Update stock quantities when new supplies arrive[cite: 1].
5. **Update Price** (`update_price`) – Modify unit prices for existing medicines[cite: 1].
6. **Delete Medicine** (`delete_medicine`) – Remove discontinued or outdated entries[cite: 1].
7. **New Sale** (`new_sale`) – Process customer purchases and record transactions[cite: 1].
8. **Sales History** (`sales_history`) – View past sales records[cite: 1].
9. **Show Alerts** (`show_alerts`) – Check low-stock or expiry notifications[cite: 1].
10. **Export CSV** (`export_csv`) – Save inventory and sales data to CSV files[cite: 1].
11. **Import CSV** (`import_csv`) – Load inventory and sales records from CSV files[cite: 1].

## Project Structure

```text
pharmacy-management-system/
├── main.py          # Core application logic and CLI menu (PharmacyApp)[cite: 1]
├── medicines.csv    # Medicine inventory dataset[cite: 1]
├── sales.csv        # Recorded sales transactions dataset[cite: 1]
└── README.md        # Project documentation
