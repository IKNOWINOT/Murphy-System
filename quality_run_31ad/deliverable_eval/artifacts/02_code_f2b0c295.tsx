```typescript
import React, { useState } from'react';
import { useForm } from'react-hook-form';

interface SettingsFormValues {
  name: string;
  email: string;
  notifications: boolean;
}

interface SettingsFormProps {
  onSubmit: (values: SettingsFormValues) => void;
  defaultValues: SettingsFormValues;
}

const SettingsForm: React.FC<SettingsFormProps> = ({ onSubmit, defaultValues }) => {
  const { register, handleSubmit, formState: { errors } } = useForm<SettingsFormValues>({
    defaultValues,
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <label>
        Name:
        <input type="text" {...register('name')} />
        {errors.name && <div>{errors.name.message}</div>}
      </label>
      <label>
        Email:
        <input type="email" {...register('email')} />
        {errors.email && <div>{errors.email.message}</div>}
      </label>
      <label>
        Notifications:
        <input type="checkbox" {...register('notifications')} />
      </label>
      <button type="submit">Save</button>
    </form>
  );
};

export default SettingsForm;
```