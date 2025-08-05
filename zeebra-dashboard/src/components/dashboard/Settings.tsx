
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Brain, Database } from 'lucide-react';
import { toast } from 'sonner';

export const Settings = () => {
  const [activeModel, setActiveModel] = useState('gemini');
  const [saveTrainingData, setSaveTrainingData] = useState(false);

  useEffect(() => {
    // Fetch current dashboard settings on mount
    const fetchSettings = async () => {
      try {
        const res = await fetch('/api/dashboard-settings');
        if (res.ok) {
          const data = await res.json();
          if (data.active_model) setActiveModel(data.active_model);
          if (typeof data.save_training_data === 'boolean') setSaveTrainingData(data.save_training_data);
        }
      } catch (e) {
        console.error('Failed to fetch dashboard settings', e);
      }
    };
    fetchSettings();
  }, []);

  const updateSettings = async (payload: { active_model?: string; save_training_data?: boolean }) => {
    try {
      const res = await fetch('/api/dashboard-settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Failed to update settings');
    } catch (e) {
      toast.error('Failed to update dashboard settings');
      console.error(e);
    }
  };

  const handleModelChange = (value: string) => {
    setActiveModel(value);
    updateSettings({ active_model: value });
    toast.success(`Active model switched to ${value === 'openai' ? 'OpenAI' : 'Gemini'}`);
  };

  const handleTrainingDataToggle = (checked: boolean) => {
    setSaveTrainingData(checked);
    updateSettings({ save_training_data: checked });
    toast.success(`Training data saving ${checked ? 'enabled' : 'disabled'}`);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-3 mb-6">
        <SettingsIcon className="w-8 h-8 text-primary" />
        <h2 className="text-3xl font-bold text-foreground">System Settings</h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="glass-effect border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Brain className="w-5 h-5 text-primary" />
              <span>AI Model Configuration</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <Label htmlFor="model-select" className="text-sm font-medium">
                Active Model
              </Label>
              <Select value={activeModel} onValueChange={handleModelChange}>
                <SelectTrigger id="model-select">
                  <SelectValue placeholder="Select AI Model" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai">OpenAI Models</SelectItem>
                  <SelectItem value="gemini">Google Gemini</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                This setting affects which AI model is used for processing requests across the system.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-secondary/20 border border-secondary">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">Current Active Model</h4>
                  <p className="text-sm text-muted-foreground">
                    {activeModel === 'openai' ? 'OpenAI GPT Models' : 'Google Gemini Models'}
                  </p>
                </div>
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                  <Brain className="w-6 h-6 text-primary" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-effect border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Database className="w-5 h-5 text-primary" />
              <span>Data Management</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="space-y-2">
                <Label htmlFor="training-data" className="text-sm font-medium">
                  Save Training Data
                </Label>
                <p className="text-xs text-muted-foreground">
                  Enable saving of frames and data for model training purposes
                </p>
              </div>
              <Switch
                id="training-data"
                checked={saveTrainingData}
                onCheckedChange={handleTrainingDataToggle}
              />
            </div>

            <div className="p-4 rounded-lg bg-secondary/20 border border-secondary">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">Training Data Status</h4>
                  <p className="text-sm text-muted-foreground">
                    {saveTrainingData ? 'Currently saving frames for training' : 'Training data collection disabled'}
                  </p>
                </div>
                <div className={`w-3 h-3 rounded-full ${saveTrainingData ? 'bg-chart-3' : 'bg-muted'}`} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
