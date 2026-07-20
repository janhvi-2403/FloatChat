
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils.argo_fetcher import get_fetcher
from models.database import get_db_connection, ArgoProfile
import json
from datetime import datetime

def ingest_from_argopy(lon_min=-75, lon_max=-45, lat_min=20, lat_max=30, 
                       time_start='2023-01-01', time_end='2023-06-01'):
    """
    Ingest data directly from argopy
    """
    print("🚀 Starting data ingestion from argopy...")
    
    try:
        # Fetch data dynamically
        fetcher = get_fetcher()
        ds = fetcher.fetch_by_region(
            lon_min=lon_min,
            lon_max=lon_max,
            lat_min=lat_min,
            lat_max=lat_max,
            time_start=time_start,
            time_end=time_end
        )
        
        # Convert to dictionary
        data = fetcher.dataset_to_dict(ds)
        print(f"📊 Fetched {data['num_profiles']} profiles")
        
        # Save to cache (optional)
        filename = f"argo_region_{time_start}_{time_end}.nc"
        fetcher.save_to_netcdf(ds, filename)
        
        # Now insert into PostgreSQL
        session = get_db_connection()
        profiles_inserted = 0
        
        for profile in data['profiles']:
            try:
                # Parse date
                date_val = None
                if profile.get('date'):
                    try:
                        date_val = datetime.fromisoformat(profile['date'].replace('Z', '+00:00'))
                    except:
                        date_val = datetime.now()
                
                db_profile = ArgoProfile(
                    float_id=profile.get('float_id', 'Unknown'),
                    date=date_val,
                    latitude=profile.get('latitude'),
                    longitude=profile.get('longitude'),
                    pressure=json.dumps(profile.get('pressure', [])),
                    temperature=json.dumps(profile.get('temperature', [])),
                    salinity=json.dumps(profile.get('salinity', [])),
                    depth=json.dumps([])  # Calculate later if needed
                )
                session.add(db_profile)
                profiles_inserted += 1
            except Exception as e:
                print(f"⚠️ Error inserting profile: {e}")
                continue
        
        session.commit()
        print(f"✅ Successfully inserted {profiles_inserted} profiles into database")
        session.close()
        
        return profiles_inserted
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 0

if __name__ == "__main__":
    print("🌊 FloatChat Data Ingestion")
    print("============================")
    print("Ingesting data for region: lon[-75, -45], lat[20, 30]")
    print("Time period: 2023-01-01 to 2023-06-01")
    print()
    
    result = ingest_from_argopy()
    
    if result > 0:
        print(f"\n🎉 Success! Inserted {result} profiles.")
    else:
        print("\n❌ Ingestion failed. Please check the error above.")
