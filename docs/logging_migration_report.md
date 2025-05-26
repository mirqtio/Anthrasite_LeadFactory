Print to Logger Migration Report
=============================

Found 41 print statements to replace.

File: /Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory/leadfactory/cost/cost_tracking.py
--------------------------------------------------------------------------------
* Already imports logging (needs to be replaced with leadfactory.utils.logging)

Line 707: print(f"Daily costs: ${costs:.2f}")
  Replace with: logger.info(f'Daily costs: ${costs:.2f}')
  Log level: info

Line 728: print(f"Monthly costs for {costs['year']}-{costs['month']}:")
  Replace with: logger.info(f"Monthly costs for {costs['year']}-{costs['month']}:")
  Log level: info

Line 729: print(f"  Budget: ${costs['budget']:.2f}")
  Replace with: logger.info(f"  Budget: ${costs['budget']:.2f}")
  Log level: info

Line 730: print(f"  Spent: ${costs['spent']:.2f}")
  Replace with: logger.info(f"  Spent: ${costs['spent']:.2f}")
  Log level: info

Line 731: print(f"  Remaining: ${costs['remaining']:.2f}")
  Replace with: logger.info(f"  Remaining: ${costs['remaining']:.2f}")
  Log level: info

Line 734: print("\nBreakdown by service:")
  Replace with: logger.info('\nBreakdown by service:')
  Log level: info

Line 713: print(f"Daily cost report exported to {args.export}")
  Replace with: logger.info(f'Daily cost report exported to {args.export}')
  Log level: info

Line 715: print(f"Failed to export daily cost report")
  Replace with: logger.error(f'Failed to export daily cost report')
  Log level: error

Line 736: print(f"  {service}: ${amount:.2f}")
  Replace with: logger.info(f'  {service}: ${amount:.2f}')
  Log level: info

Line 742: print(f"Monthly cost report exported to {args.export}")
  Replace with: logger.info(f'Monthly cost report exported to {args.export}')
  Log level: info

Line 744: print(f"Failed to export monthly cost report")
  Replace with: logger.error(f'Failed to export monthly cost report')
  Log level: error

Line 753: print(f"Monthly budget set to ${args.amount:.2f}")
  Replace with: logger.info(f'Monthly budget set to ${args.amount:.2f}')
  Log level: info

Line 755: print(f"Failed to set monthly budget")
  Replace with: logger.error(f'Failed to set monthly budget')
  Log level: error


File: /Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory/leadfactory/cost/budget_audit.py
--------------------------------------------------------------------------------
* Already imports logging (needs to be replaced with leadfactory.utils.logging)

Line 54: print(f"{Colors.HEADER}{text}{Colors.ENDC}")
  Replace with: logger.info(f'{Colors.HEADER}{text}{Colors.ENDC}')
  Log level: info

Line 58: print(f"{Colors.OKGREEN}{text}{Colors.ENDC}")
  Replace with: logger.info(f'{Colors.OKGREEN}{text}{Colors.ENDC}')
  Log level: info

Line 62: print(f"{Colors.WARNING}{text}{Colors.ENDC}")
  Replace with: logger.info(f'{Colors.WARNING}{text}{Colors.ENDC}')
  Log level: info

Line 66: print(f"{Colors.FAIL}{text}{Colors.ENDC}")
  Replace with: logger.info(f'{Colors.FAIL}{text}{Colors.ENDC}')
  Log level: info

Line 83: print(f"Daily cost: {format_currency(cost_tracker.get_daily_cost())}")
  Replace with: logger.info(f'Daily cost: {format_currency(cost_tracker.get_daily_cost())}')
  Log level: info

Line 84: print(f"Monthly cost: {format_currency(cost_tracker.get_monthly_cost())}")
  Replace with: logger.info(f'Monthly cost: {format_currency(cost_tracker.get_monthly_cost())}')
  Log level: info

Line 134: print(f"Enabled: {budget_gate.enabled}")
  Replace with: logger.info(f'Enabled: {budget_gate.enabled}')
  Log level: info

Line 135: print(f"Override: {budget_gate.override}")
  Replace with: logger.info(f'Override: {budget_gate.override}')
  Log level: info

Line 136: print(f"Threshold: {format_currency(budget_gate.threshold)}")
  Replace with: logger.info(f'Threshold: {format_currency(budget_gate.threshold)}')
  Log level: info

Line 88: print(f"Budget threshold: {format_currency(budget_gate.threshold)}")
  Replace with: logger.info(f'Budget threshold: {format_currency(budget_gate.threshold)}')
  Log level: info

Line 113: print("No cost data available")
  Replace with: logger.info('No cost data available')
  Log level: info

Line 118: print(f"{service}: {format_currency(service_total)}")
  Replace with: logger.info(f'{service}: {format_currency(service_total)}')
  Log level: info

Line 121: print(f"  {operation}: {format_currency(cost)} ({format_percentage(percentage)})")
  Replace with: logger.info(f'  {operation}: {format_currency(cost)} ({format_percentage(percentage)})')
  Log level: info


File: /Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory/leadfactory/cost/budget_gate.py
--------------------------------------------------------------------------------
* Already imports logging (needs to be replaced with leadfactory.utils.logging)

Line 218: print(f"Budget gate is {'active' if is_active else 'inactive'}")
  Replace with: logger.info(f"Budget gate is {('active' if is_active else 'inactive')}")
  Log level: info

Line 219: print(f"  Enabled: {budget_gate.enabled}")
  Replace with: logger.info(f'  Enabled: {budget_gate.enabled}')
  Log level: info

Line 220: print(f"  Override: {budget_gate.override}")
  Replace with: logger.info(f'  Override: {budget_gate.override}')
  Log level: info

Line 221: print(f"  Threshold: ${budget_gate.threshold:.2f}")
  Replace with: logger.info(f'  Threshold: ${budget_gate.threshold:.2f}')
  Log level: info

Line 224: print(f"  Monthly cost: ${monthly_cost:.2f}")
  Replace with: logger.info(f'  Monthly cost: ${monthly_cost:.2f}')
  Log level: info

Line 226: print("  Monthly cost: Unknown (cost tracker not available)")
  Replace with: logger.info('  Monthly cost: Unknown (cost tracker not available)')
  Log level: info

Line 240: print("Skipped operations:")
  Replace with: logger.info('Skipped operations:')
  Log level: info

Line 244: print("No operations have been skipped")
  Replace with: logger.info('No operations have been skipped')
  Log level: info

Line 242: print(f"  {op}: {count}")
  Replace with: logger.info(f'  {op}: {count}')
  Log level: info


File: /Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory/leadfactory/utils/metrics.py
--------------------------------------------------------------------------------
* Already imports logging (needs to be replaced with leadfactory.utils.logging)

Line 21: print("Metrics not available")
  Replace with: logger.info('Metrics not available')
  Log level: info

Line 109: print("Metrics not available - install prometheus_client package")
  Replace with: logger.info('Metrics not available - install prometheus_client package')
  Log level: info

Line 114: print(f"Metrics server started on port {args.port}")
  Replace with: logger.info(f'Metrics server started on port {args.port}')
  Log level: info

Line 115: print("Press Ctrl+C to exit")
  Replace with: logger.info('Press Ctrl+C to exit')
  Log level: info

Line 119: print("Shutting down metrics server")
  Replace with: logger.info('Shutting down metrics server')
  Log level: info

Line 121: print(f"Error: {e}")
  Replace with: logger.error(f'Error: {e}')
  Log level: error
