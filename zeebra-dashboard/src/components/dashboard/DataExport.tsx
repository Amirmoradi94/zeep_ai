
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Download, FileImage, FileSpreadsheet, Package } from 'lucide-react';
import { toast } from 'sonner';

export const DataExport = () => {
  const handleDownloadImages = async () => {
    toast.success('Preparing image download...');
    // Here you would implement the actual download logic
    // This would connect to your /saved_images endpoint
    console.log('Downloading images from /saved_images');
    
    // Simulate download preparation
    setTimeout(() => {
      toast.success('Images download started! Check your downloads folder.');
    }, 2000);
  };

  const handleDownloadQueries = async () => {
    toast.success('Preparing CSV export...');
    // Here you would implement the actual CSV export logic
    // This would query the queries table and generate a CSV file
    console.log('Exporting queries table to CSV');
    
    // Simulate CSV generation
    setTimeout(() => {
      toast.success('Queries CSV export completed! Check your downloads folder.');
    }, 1500);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-3 mb-6">
        <Download className="w-8 h-8 text-primary" />
        <h2 className="text-3xl font-bold text-foreground">Data Export</h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="glass-effect border-border/50 hover:border-primary/50 transition-all duration-300">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <FileImage className="w-5 h-5 text-chart-1" />
              <span>Download Saved Images</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Download all saved images from the /saved_images directory as a compressed ZIP file. 
              This includes all training frames and processed images.
            </p>
            
            <div className="p-4 rounded-lg bg-secondary/20 border border-secondary">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">Available Images</h4>
                  <p className="text-sm text-muted-foreground">Estimated size: ~2.3GB</p>
                </div>
                <Package className="w-8 h-8 text-chart-1" />
              </div>
            </div>

            <Button 
              onClick={handleDownloadImages}
              className="w-full"
              size="lg"
            >
              <Download className="w-4 h-4 mr-2" />
              Download Images as ZIP
            </Button>
          </CardContent>
        </Card>

        <Card className="glass-effect border-border/50 hover:border-primary/50 transition-all duration-300">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <FileSpreadsheet className="w-5 h-5 text-chart-3" />
              <span>Export Queries Data</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Export all saved queries from the database as a CSV file. 
              This includes user queries, generated responses, and feedback data.
            </p>
            
            <div className="p-4 rounded-lg bg-secondary/20 border border-secondary">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">Available Records</h4>
                  <p className="text-sm text-muted-foreground">~145,320 queries</p>
                </div>
                <FileSpreadsheet className="w-8 h-8 text-chart-3" />
              </div>
            </div>

            <Button 
              onClick={handleDownloadQueries}
              className="w-full"
              size="lg"
              variant="outline"
            >
              <Download className="w-4 h-4 mr-2" />
              Export Queries as CSV
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
