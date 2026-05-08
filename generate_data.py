import pandas as pd
import numpy as np

np.random.seed(42)

programme_patterns = {
    1: {'min_points': 0},
    2: {'min_points': 30},
    20: {'min_points': 30},
    28: {'min_points': 30},
    29: {'min_points': 30},
    30: {'min_points': 30},
}

data = []
programmes = list(programme_patterns.keys())
records_per_prog = 500 // len(programmes)
extra = 500 % len(programmes)

for i, pid in enumerate(programmes):
    count = records_per_prog + (1 if i < extra else 0)
    min_pts = programme_patterns[pid]['min_points']
   
    for _ in range(count):
        subjects_count = np.random.randint(6, 10)
        total_points = np.random.randint(20, 45)
       
        eligible = 1
        if total_points < min_pts or subjects_count < 6:
            eligible = 0
           
        data.append([pid, subjects_count, total_points, eligible])

df = pd.DataFrame(data, columns=['programme_id', 'subjects_count', 'total_points', 'eligible'])
df.to_excel('programme_training_data_500.xlsx', index=False)

print("File saved successfully!")
print("Shape:", df.shape)
print("\nEligible distribution:")
print(df['eligible'].value_counts())
