export interface Flow {
  id: number;
  name: string;
  description?: string;
  nodes: any;
  edges: any;
  viewport?: any;
  data?: any;
  is_template: boolean;
  tags?: string[];
  created_at: string;
  updated_at?: string;
} 