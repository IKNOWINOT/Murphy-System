```python
def calculate_total_revenue(data):
    # Initialize total revenue to 0
    total_revenue = 0
    
    # Iterate over each item in the data list
    for item in data:
        # Check if 'price' and 'quantity' exist and are non-negative
        if 'price' in item and 'quantity' in item and item['price'] >= 0 and item['quantity'] >= 0:
            # Add revenue to total revenue
            total_revenue += item['price'] * item['quantity']
    
    # Return the total revenue
    return total_revenue

# Example usage:
data = [
    {'price': 10, 'quantity': 2},
    {'price': -5, 'quantity': 3},  # ignored due to negative price
    {'quantity': 4},  # ignored due to missing price
    {'price': 7, 'quantity': -2},  # ignored due to negative quantity
    {'price': 8, 'quantity': 1}
]
print(calculate_total_revenue(data))  # Output: 10*2 + 8*1 = 28
```